"""Đơn vận chuyển: thông tin người nhận, hàng gửi, phạm vi truy cập và trạng thái."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
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

from app.customers import Address, Name, Phone, PositiveID
from app.infrastructure.db.session import get_session

Status = Literal['PENDING', 'CONFIRMED', 'SHIPPING', 'DELIVERED', 'CANCELLED']
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
Note = Annotated[str, StringConstraints(max_length=2000)]
ItemName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
OrderCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^[A-Za-z0-9_-]{3,40}$')]
OrderID = Annotated[int, Path(gt=0, le=9223372036854775807)]


class OrderItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: ItemName
    quantity: int = Field(strict=True, gt=0, le=2147483647)
    note: Note | None = None


Items = Annotated[list[OrderItem], Field(min_length=1, max_length=100)]


class OrderCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customer_id: PositiveID
    recipient_name: Name
    recipient_phone: Phone
    recipient_address: Address
    items: Items
    shipping_fee: Money = Decimal(0)
    note: Note | None = None
    order_code: OrderCode | None = None

    @field_validator('order_code')
    @classmethod
    def uppercase_code(cls, value):
        return value.upper() if value is not None else None


class OrderUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    recipient_name: Name | None = None
    recipient_phone: Phone | None = None
    recipient_address: Address | None = None
    shipping_fee: Money | None = None
    note: Note | None = None
    items: Items | None = None

    @model_validator(mode='after')
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError('Cần ít nhất một trường cập nhật')
        for field in self.model_fields_set - {'note'}:
            if getattr(self, field) is None:
                raise ValueError(f'{field} không được null')
        return self


class OrderStatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Status


def order_row(row):
    data = dict(row)
    data['shipping_fee'] = str(data['shipping_fee'])
    for key in ('created_at', 'updated_at'):
        if isinstance(data[key], datetime):
            data[key] = data[key].replace(tzinfo=timezone.utc).isoformat()
    if 'items' in data:
        if isinstance(data['items'], (str, bytes)):
            data['items'] = json.loads(data['items'])
        data['items'].sort(key=lambda item: item['id'])
    return data


def order_database_error(exc):
    code = exc.orig.args[0]
    if code == 1062:
        raise HTTPException(409, 'Mã đơn đã tồn tại') from None
    if code in (1205, 1213):
        raise HTTPException(409, 'Đơn đang được cập nhật đồng thời, vui lòng thử lại') from None
    if code == 1451:
        raise HTTPException(409, 'Hàng gửi đã được đóng kiện, không thể thay thế') from None
    if code == 1644:
        status, detail = {
            'FORBIDDEN': (403, 'Không có quyền thao tác đơn vận chuyển'),
            'NOT_FOUND': (404, 'Không tìm thấy đơn hoặc khách hàng trong phạm vi truy cập'),
            'INACTIVE_CUSTOMER': (409, 'Không thể tạo đơn cho khách đã ngừng hoạt động'),
            'INVALID_ITEMS': (422, 'Danh sách hàng gửi không hợp lệ'),
            'INVALID_FEE': (422, 'Phí vận chuyển không hợp lệ'),
            'INVALID_STATUS': (422, 'Trạng thái không hợp lệ'),
            'ORDER_NOT_EDITABLE': (409, 'Chỉ được sửa đơn đang PENDING'),
            'INVALID_TRANSITION': (409, 'Không được chuyển trạng thái theo hướng này'),
            'ORDER_HAS_DEPENDENCIES': (409, 'Đơn đã có kiện hàng hoặc giao dịch liên quan'),
            'PACKAGE_PROGRESS_MISMATCH': (409, 'Trạng thái đơn phải khớp tiến độ thực tế của các kiện'),
        }.get(str(exc.orig.args[1]), (409, 'Không thể xử lý đơn vận chuyển'))
        raise HTTPException(status, detail) from None
    raise exc


def create_order_router(current_user):
    router = APIRouter(prefix='/orders', tags=['Orders'])

    async def reader(user: Annotated[dict, Depends(current_user)]):
        if user['role'] not in ('ADMIN', 'SALE', 'CUSTOMER', 'WAREHOUSE'):
            raise HTTPException(403, 'Không có quyền truy cập đơn vận chuyển')
        return user

    async def writer(user: Annotated[dict, Depends(reader)]):
        if user['role'] not in ('ADMIN', 'SALE'):
            raise HTTPException(403, 'Chỉ ADMIN hoặc SALE được quản lý đơn vận chuyển')
        return user

    @router.post('', status_code=201)
    async def create_order(body: OrderCreate, actor: Annotated[dict, Depends(writer)],
                           session: Annotated[AsyncSession, Depends(get_session)]):
        params = body.model_dump(mode='json')
        params['order_code'] = body.order_code or 'DH' + uuid4().hex.upper()
        params['items'] = json.dumps(params['items'], ensure_ascii=False)
        params['actor'] = actor['id']
        try:
            result = await session.execute(text('''CALL sp_create_order(
                :actor,:order_code,:customer_id,:recipient_name,:recipient_phone,
                :recipient_address,:shipping_fee,:note,:items)'''), params)
            row = order_row(result.mappings().one())
            await session.commit()
            return row
        except DBAPIError as exc:
            await session.rollback()
            order_database_error(exc)

    @router.get('')
    async def list_orders(
        actor: Annotated[dict, Depends(reader)],
        session: Annotated[AsyncSession, Depends(get_session)],
        customer_id: PositiveID | None = None, status: Status | None = None,
        search: str | None = Query(default=None, max_length=150),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
    ):
        try:
            result = await session.execute(text(
                'CALL sp_list_orders(:actor,:customer,:status,:search,:limit,:offset)'),
                {'actor': actor['id'], 'customer': customer_id, 'status': status,
                 'search': search.strip() if search else None, 'limit': limit, 'offset': offset})
            return {'items': [order_row(row) for row in result.mappings().all()],
                    'limit': limit, 'offset': offset}
        except DBAPIError as exc:
            order_database_error(exc)

    @router.get('/{order_id}')
    async def get_order(order_id: OrderID, actor: Annotated[dict, Depends(reader)],
                        session: Annotated[AsyncSession, Depends(get_session)]):
        try:
            result = await session.execute(text('CALL sp_get_order(:actor,:id)'),
                                           {'actor': actor['id'], 'id': order_id})
            row = result.mappings().first()
            if row is None:
                raise HTTPException(404, 'Không tìm thấy đơn trong phạm vi truy cập')
            return order_row(row)
        except DBAPIError as exc:
            order_database_error(exc)

    @router.patch('/{order_id}')
    async def update_order(order_id: OrderID, body: OrderUpdate, actor: Annotated[dict, Depends(writer)],
                           session: Annotated[AsyncSession, Depends(get_session)]):
        try:
            result = await session.execute(text('CALL sp_update_order(:actor,:id,:patch)'),
                {'actor': actor['id'], 'id': order_id, 'patch': body.model_dump_json(exclude_unset=True)})
            row = order_row(result.mappings().one())
            await session.commit()
            return row
        except DBAPIError as exc:
            await session.rollback()
            order_database_error(exc)

    @router.patch('/{order_id}/status')
    async def update_order_status(order_id: OrderID, body: OrderStatusUpdate,
                                  actor: Annotated[dict, Depends(writer)], session: Annotated[AsyncSession, Depends(get_session)]):
        try:
            result = await session.execute(text('CALL sp_update_order_status(:actor,:id,:status)'),
                {'actor': actor['id'], 'id': order_id, 'status': body.status})
            row = order_row(result.mappings().one())
            await session.commit()
            return row
        except DBAPIError as exc:
            await session.rollback()
            order_database_error(exc)

    return router
