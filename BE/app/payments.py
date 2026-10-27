"""Ghi nhận thu/hoàn phí vận chuyển, sổ giao dịch bất biến và số dư theo đơn."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.validation import PositiveID
from app.infrastructure.db.session import get_session

PaymentMethod = Literal["CASH", "BANK_TRANSFER"]
TransactionType = Literal["PAYMENT", "REFUND"]
Amount = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
Reference = Annotated[
    str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z0-9_.:/-]{3,80}$")
]
ResourceID = Annotated[int, Path(gt=0, le=9223372036854775807)]


class PaymentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: PositiveID
    amount: Amount
    method: PaymentMethod
    reference_code: Reference

    @field_validator("reference_code")
    @classmethod
    def uppercase_reference(cls, value):
        return value.upper()


def payment_row(row):
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, Decimal):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.replace(tzinfo=timezone.utc).isoformat()
    if "replayed" in result:
        result["replayed"] = bool(result["replayed"])
    return result


def payment_error(exc):
    code = exc.orig.args[0]
    if code == 1062:
        raise HTTPException(409, "Mã tham chiếu đang được dùng cho giao dịch khác") from None
    if code in (1205, 1213):
        raise HTTPException(
            409, "Đơn đang được cập nhật đồng thời, vui lòng thử lại với cùng mã tham chiếu"
        ) from None
    if code == 1644:
        status, detail = {
            "FORBIDDEN": (403, "Không có quyền xem hoặc ghi giao dịch"),
            "NOT_FOUND": (404, "Không tìm thấy đơn hoặc giao dịch trong phạm vi truy cập"),
            "INVALID_PAYMENT": (422, "Dữ liệu giao dịch không hợp lệ"),
            "REFERENCE_CONFLICT": (409, "Mã tham chiếu đã tồn tại nhưng thông tin giao dịch khác"),
            "ORDER_NOT_PAYABLE": (409, "Chỉ thu tiền cho đơn CONFIRMED, SHIPPING hoặc DELIVERED"),
            "OVERPAYMENT": (409, "Số tiền thu vượt phí vận chuyển còn phải thu"),
            "OVER_REFUND": (409, "Số tiền hoàn vượt số đã thu ròng"),
            "LEDGER_INCONSISTENT": (
                409,
                "Dữ liệu thu/hoàn cũ không hợp lệ, cần quản trị viên đối soát",
            ),
        }.get(str(exc.orig.args[1]), (409, "Không thể xử lý giao dịch"))
        raise HTTPException(status, detail) from None
    raise exc


async def read_one(session, statement, params):
    try:
        result = await session.execute(text(statement), params)
        row = result.mappings().first()
        if row is None:
            raise HTTPException(404, "Không tìm thấy đơn hoặc giao dịch trong phạm vi truy cập")
        return payment_row(row)
    except DBAPIError as exc:
        await session.rollback()
        payment_error(exc)


async def record_payment(session, actor_id, body, transaction_type):
    try:
        result = await session.execute(
            text("CALL sp_record_payment(:actor,:order_id,:amount,:type,:method,:reference_code)"),
            {"actor": actor_id, "type": transaction_type, **body.model_dump(mode="json")},
        )
        row = payment_row(result.mappings().one())
        await session.commit()
        return row
    except DBAPIError as exc:
        await session.rollback()
        payment_error(exc)


def create_payment_router(current_user):
    router = APIRouter(tags=["Payments"])

    async def reader(user: Annotated[dict, Depends(current_user)]):
        if user["role"] not in ("ADMIN", "ACCOUNTANT", "SALE", "CUSTOMER"):
            raise HTTPException(403, "Không có quyền xem giao dịch")
        return user

    async def writer(user: Annotated[dict, Depends(reader)]):
        if user["role"] not in ("ADMIN", "ACCOUNTANT"):
            raise HTTPException(403, "Chỉ ADMIN hoặc ACCOUNTANT được ghi nhận thu/hoàn tiền")
        return user

    Session = Annotated[AsyncSession, Depends(get_session)]
    Reader = Annotated[dict, Depends(reader)]
    Writer = Annotated[dict, Depends(writer)]

    @router.post("/payments", status_code=201)
    async def create_payment(
        body: PaymentCreate, response: Response, actor: Writer, session: Session
    ):
        row = await record_payment(session, actor["id"], body, "PAYMENT")
        if row["replayed"]:
            response.status_code = 200
        return row

    @router.post("/payments/refunds", status_code=201)
    async def create_refund(
        body: PaymentCreate, response: Response, actor: Writer, session: Session
    ):
        row = await record_payment(session, actor["id"], body, "REFUND")
        if row["replayed"]:
            response.status_code = 200
        return row

    @router.get("/payments")
    async def list_payments(
        actor: Reader,
        session: Session,
        order_id: PositiveID | None = None,
        transaction_type: TransactionType | None = None,
        method: PaymentMethod | None = None,
        date_from: AwareDatetime | None = None,
        date_to: AwareDatetime | None = None,
        search: str | None = Query(default=None, max_length=80),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
    ):
        if date_from and date_to and date_from > date_to:
            raise HTTPException(422, "date_from không được sau date_to")
        params = {
            "actor": actor["id"],
            "order": order_id,
            "type": transaction_type,
            "method": method,
            "start": date_from.astimezone(timezone.utc).replace(tzinfo=None) if date_from else None,
            "end": date_to.astimezone(timezone.utc).replace(tzinfo=None) if date_to else None,
            "search": search.strip() if search else None,
            "limit": limit,
            "offset": offset,
        }
        try:
            result = await session.execute(
                text(
                    "CALL sp_list_payments(:actor,:order,:type,:method,:start,:end,:search,:limit,:offset)"
                ),
                params,
            )
            return {
                "items": [payment_row(row) for row in result.mappings().all()],
                "limit": limit,
                "offset": offset,
            }
        except DBAPIError as exc:
            await session.rollback()
            payment_error(exc)

    @router.get("/payments/{payment_id}")
    async def get_payment(payment_id: ResourceID, actor: Reader, session: Session):
        return await read_one(
            session, "CALL sp_get_payment(:actor,:id)", {"actor": actor["id"], "id": payment_id}
        )

    @router.get("/orders/{order_id}/payment-summary")
    async def order_payment_summary(order_id: ResourceID, actor: Reader, session: Session):
        return await read_one(
            session,
            "CALL sp_order_payment_summary(:actor,:order)",
            {"actor": actor["id"], "order": order_id},
        )

    return router
