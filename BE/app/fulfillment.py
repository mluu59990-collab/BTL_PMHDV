"""Kho, đóng kiện và vận chuyển: HTTP validation, RBAC và procedure MySQL."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validation import Address, Name, Note, PositiveID
from app.infrastructure.db.session import get_session

ResourceID = Annotated[int, Path(gt=0, le=9223372036854775807)]
Weight = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3, allow_inf_nan=False)]
Dimension = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2, allow_inf_nan=False)]
PackageStatus = Literal["CREATED", "IN_WAREHOUSE", "IN_TRANSIT", "DELIVERED", "CANCELLED"]
WarehouseCode = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{2,30}$")
]
TrackingCode = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_-]{3,50}$")
]


class WarehouseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouse_code: WarehouseCode
    name: Name
    address: Address
    country_code: Literal["CN", "VN"]

    @field_validator("warehouse_code", "country_code", mode="before")
    @classmethod
    def uppercase(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class WarehouseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    address: Address | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Cần ít nhất một trường cập nhật không null")
        return self


class PackageItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_item_id: PositiveID
    quantity: int = Field(strict=True, gt=0, le=2147483647)


PackageItems = Annotated[list[PackageItem], Field(min_length=1, max_length=100)]


class PackageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: PositiveID
    weight_kg: Weight
    length_cm: Dimension
    width_cm: Dimension
    height_cm: Dimension
    items: PackageItems
    tracking_code: TrackingCode | None = None
    note: Note | None = None

    @field_validator("tracking_code")
    @classmethod
    def uppercase(cls, value):
        return value.upper() if value is not None else None

    @field_validator("items")
    @classmethod
    def unique_items(cls, value):
        if len({item.order_item_id for item in value}) != len(value):
            raise ValueError("Mỗi dòng hàng chỉ xuất hiện một lần trong kiện")
        return value


class PackageUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight_kg: Weight | None = None
    length_cm: Dimension | None = None
    width_cm: Dimension | None = None
    height_cm: Dimension | None = None
    items: PackageItems | None = None

    @model_validator(mode="after")
    def valid_patch(self):
        if not self.model_fields_set or any(
            getattr(self, key) is None for key in self.model_fields_set
        ):
            raise ValueError("Cần ít nhất một trường cập nhật không null")
        if self.items is not None:
            PackageCreate.unique_items(self.items)
        return self


class PackageStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: PackageStatus
    warehouse_id: PositiveID | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def valid_warehouse(self):
        if (self.status == "IN_WAREHOUSE") != (self.warehouse_id is not None):
            raise ValueError(
                "Chỉ IN_WAREHOUSE yêu cầu warehouse_id; trạng thái khác phải bỏ hoặc để null"
            )
        return self


def fulfillment_row(row):
    data = dict(row)
    for key, value in data.items():
        if isinstance(value, Decimal):
            data[key] = str(value)
        elif isinstance(value, datetime):
            data[key] = value.replace(tzinfo=timezone.utc).isoformat()
    if "is_active" in data:
        data["is_active"] = bool(data["is_active"])
    if "items" in data:
        if isinstance(data["items"], (str, bytes)):
            data["items"] = json.loads(data["items"])
        data["items"].sort(key=lambda item: item["id"])
    return data


def fulfillment_error(exc):
    code = exc.orig.args[0]
    if code == 1062:
        raise HTTPException(
            409, "Mã kho, mã vận đơn hoặc dòng hàng trong kiện đã tồn tại"
        ) from None
    if code in (1205, 1213):
        raise HTTPException(409, "Dữ liệu đang được cập nhật đồng thời, vui lòng thử lại") from None
    if code == 1644:
        status, detail = {
            "FORBIDDEN": (403, "Không có quyền thao tác kho/kiện hàng"),
            "NOT_FOUND": (404, "Không tìm thấy dữ liệu trong phạm vi truy cập"),
            "WAREHOUSE_OCCUPIED": (
                409,
                "Kho còn kiện, cần xuất hết kiện trước khi ngừng hoạt động",
            ),
            "ORDER_NOT_PACKABLE": (409, "Chỉ đóng/xử lý kiện của đơn CONFIRMED hoặc SHIPPING"),
            "PACKAGE_NOT_EDITABLE": (409, "Chỉ sửa kiện CREATED của đơn CONFIRMED hoặc SHIPPING"),
            "INVALID_PACKAGE_ITEMS": (422, "Danh sách hàng đóng kiện không hợp lệ"),
            "ITEM_NOT_IN_ORDER": (422, "Dòng hàng không thuộc đơn của kiện"),
            "OVER_PACKED": (409, "Số lượng đóng kiện vượt số lượng còn lại trong đơn"),
            "INVALID_PACKAGE_STATUS": (422, "Trạng thái hoặc warehouse_id không hợp lệ"),
            "INVALID_PACKAGE_TRANSITION": (
                409,
                "Không được chuyển trạng thái hoặc đổi kho trực tiếp theo hướng này",
            ),
            "INVALID_WAREHOUSE": (422, "Kho không tồn tại hoặc đã ngừng hoạt động"),
        }.get(str(exc.orig.args[1]), (409, "Không thể xử lý kho/kiện hàng"))
        raise HTTPException(status, detail) from None
    raise exc


async def one(session, statement, params, *, write=False):
    try:
        result = await session.execute(text(statement), params)
        row = result.mappings().first()
        if row is None:
            raise HTTPException(404, "Không tìm thấy dữ liệu trong phạm vi truy cập")
        data = fulfillment_row(row)
        if write:
            await session.commit()
        return data
    except DBAPIError as exc:
        await session.rollback()
        fulfillment_error(exc)


async def many(session, statement, params, limit, offset):
    try:
        result = await session.execute(text(statement), params)
        return {
            "items": [fulfillment_row(row) for row in result.mappings().all()],
            "limit": limit,
            "offset": offset,
        }
    except DBAPIError as exc:
        await session.rollback()
        fulfillment_error(exc)


def create_fulfillment_router(current_user):
    router = APIRouter(tags=["Warehouses and Packages"])

    async def reader(user: Annotated[dict, Depends(current_user)]):
        if user["role"] not in ("ADMIN", "WAREHOUSE", "SALE", "CUSTOMER"):
            raise HTTPException(403, "Không có quyền xem kho/kiện hàng")
        return user

    async def operator(user: Annotated[dict, Depends(reader)]):
        if user["role"] not in ("ADMIN", "WAREHOUSE"):
            raise HTTPException(403, "Chỉ ADMIN hoặc WAREHOUSE được xử lý kiện")
        return user

    async def administrator(user: Annotated[dict, Depends(reader)]):
        if user["role"] != "ADMIN":
            raise HTTPException(403, "Chỉ ADMIN được quản lý thông tin kho")
        return user

    Session = Annotated[AsyncSession, Depends(get_session)]
    Reader = Annotated[dict, Depends(reader)]
    Operator = Annotated[dict, Depends(operator)]
    Administrator = Annotated[dict, Depends(administrator)]

    @router.post("/warehouses", status_code=201)
    async def create_warehouse(body: WarehouseCreate, actor: Administrator, session: Session):
        return await one(
            session,
            "CALL sp_create_warehouse(:actor,:warehouse_code,:name,:address,:country_code)",
            {"actor": actor["id"], **body.model_dump(mode="json")},
            write=True,
        )

    @router.get("/warehouses")
    async def list_warehouses(
        actor: Reader,
        session: Session,
        active_only: bool = True,
        search: str | None = Query(default=None, max_length=150),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
    ):
        return await many(
            session,
            "CALL sp_list_warehouses(:actor,:active,:search,:limit,:offset)",
            {
                "actor": actor["id"],
                "active": active_only,
                "search": search.strip() if search else None,
                "limit": limit,
                "offset": offset,
            },
            limit,
            offset,
        )

    @router.get("/warehouses/{warehouse_id}")
    async def get_warehouse(warehouse_id: ResourceID, actor: Reader, session: Session):
        return await one(
            session, "CALL sp_get_warehouse(:actor,:id)", {"actor": actor["id"], "id": warehouse_id}
        )

    @router.patch("/warehouses/{warehouse_id}")
    async def update_warehouse(
        warehouse_id: ResourceID, body: WarehouseUpdate, actor: Administrator, session: Session
    ):
        return await one(
            session,
            "CALL sp_update_warehouse(:actor,:id,:patch)",
            {
                "actor": actor["id"],
                "id": warehouse_id,
                "patch": body.model_dump_json(exclude_unset=True),
            },
            write=True,
        )

    @router.delete("/warehouses/{warehouse_id}", status_code=204)
    async def deactivate_warehouse(
        warehouse_id: ResourceID, actor: Administrator, session: Session
    ):
        await one(
            session,
            "CALL sp_update_warehouse(:actor,:id,:patch)",
            {"actor": actor["id"], "id": warehouse_id, "patch": '{"is_active":false}'},
            write=True,
        )
        return Response(status_code=204)

    @router.post("/packages", status_code=201)
    async def create_package(body: PackageCreate, actor: Operator, session: Session):
        values = body.model_dump(mode="json")
        return await one(
            session,
            "CALL sp_create_package(:actor,:order,:code,:metrics,:items,:note)",
            {
                "actor": actor["id"],
                "order": body.order_id,
                "code": body.tracking_code or "VD" + uuid4().hex.upper(),
                "metrics": body.model_dump_json(
                    exclude={"items", "order_id", "tracking_code", "note"}
                ),
                "items": json.dumps(values["items"]),
                "note": body.note,
            },
            write=True,
        )

    @router.get("/packages")
    async def list_packages(
        actor: Reader,
        session: Session,
        order_id: PositiveID | None = None,
        warehouse_id: PositiveID | None = None,
        status: PackageStatus | None = None,
        search: str | None = Query(default=None, max_length=150),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
    ):
        return await many(
            session,
            "CALL sp_list_packages(:actor,:order,:warehouse,:status,:search,:limit,:offset)",
            {
                "actor": actor["id"],
                "order": order_id,
                "warehouse": warehouse_id,
                "status": status,
                "search": search.strip() if search else None,
                "limit": limit,
                "offset": offset,
            },
            limit,
            offset,
        )

    @router.get("/packages/{package_id}")
    async def get_package(package_id: ResourceID, actor: Reader, session: Session):
        return await one(
            session, "CALL sp_get_package(:actor,:id)", {"actor": actor["id"], "id": package_id}
        )

    @router.patch("/packages/{package_id}")
    async def update_package(
        package_id: ResourceID, body: PackageUpdate, actor: Operator, session: Session
    ):
        return await one(
            session,
            "CALL sp_update_package(:actor,:id,:patch)",
            {
                "actor": actor["id"],
                "id": package_id,
                "patch": body.model_dump_json(exclude_unset=True),
            },
            write=True,
        )

    @router.patch("/packages/{package_id}/status")
    async def update_package_status(
        package_id: ResourceID, body: PackageStatusUpdate, actor: Operator, session: Session
    ):
        return await one(
            session,
            "CALL sp_update_package_status(:actor,:id,:status,:warehouse_id,:note)",
            {"actor": actor["id"], "id": package_id, **body.model_dump(mode="json")},
            write=True,
        )

    @router.get("/packages/{package_id}/history")
    async def package_history(
        package_id: ResourceID,
        actor: Reader,
        session: Session,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
    ):
        return await many(
            session,
            "CALL sp_package_history(:actor,:id,:limit,:offset)",
            {"actor": actor["id"], "id": package_id, "limit": limit, "offset": offset},
            limit,
            offset,
        )

    return router
