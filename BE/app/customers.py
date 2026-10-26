"""API khách hàng: schema HTTP, giới hạn vai trò và gọi procedure có phạm vi dữ liệu."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_session

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r'^\+?[0-9]{8,15}$')]
PositiveID = Annotated[int, Field(gt=0, le=9223372036854775807)]


class CustomerCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name
    phone: Phone
    address: Address
    email: EmailStr | None = None
    user_id: PositiveID | None = None
    sale_id: PositiveID | None = None


class CustomerUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: Name | None = None
    phone: Phone | None = None
    address: Address | None = None
    email: EmailStr | None = None
    user_id: PositiveID | None = None
    sale_id: PositiveID | None = None
    is_active: bool | None = None

    @model_validator(mode='after')
    def valid_patch(self):
        if not self.model_fields_set:
            raise ValueError('Cần ít nhất một trường cập nhật')
        for key in ('name', 'phone', 'address', 'is_active'):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f'{key} không được null')
        return self


def customer_row(row):
    result = dict(row)
    result['is_active'] = bool(result['is_active'])
    for key in ('created_at', 'updated_at'):
        if isinstance(result[key], datetime):
            result[key] = result[key].replace(tzinfo=timezone.utc).isoformat()
    return result


def database_error(exc):
    code = exc.orig.args[0]
    if code == 1062:
        raise HTTPException(409, 'Tài khoản đã liên kết với một khách hàng') from None
    if code == 1644:
        status, detail = {
            'FORBIDDEN': (403, 'Không có quyền thao tác khách hàng'),
            'NOT_FOUND': (404, 'Không tìm thấy khách hàng trong phạm vi truy cập'),
            'INVALID_CUSTOMER_USER': (422, 'user_id phải là tài khoản CUSTOMER đang hoạt động'),
            'INVALID_SALE': (422, 'sale_id phải là tài khoản SALE đang hoạt động'),
        }.get(str(exc.orig.args[1]), (409, 'Không thể cập nhật khách hàng'))
        raise HTTPException(status, detail) from None
    raise exc


def create_customer_router(current_user):
    # Truyền dependency từ main.py để dùng chung xác thực, không tạo import vòng.
    router = APIRouter(prefix='/customers', tags=['Customers'])

    async def reader(user=Depends(current_user)):
        if user['role'] not in ('ADMIN', 'SALE', 'CUSTOMER'):
            raise HTTPException(403, 'Không có quyền truy cập khách hàng')
        return user

    async def writer(user=Depends(reader)):
        if user['role'] == 'CUSTOMER':
            raise HTTPException(403, 'CUSTOMER chỉ được xem thông tin của mình')
        return user

    @router.get('')
    async def list_customers(
        search: str | None = Query(default=None, max_length=150),
        active_only: bool = True,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0, le=2147483647),
        actor=Depends(reader), session: AsyncSession = Depends(get_session),
    ):
        try:
            result = await session.execute(text('CALL sp_list_customers(:actor,:search,:active,:limit,:offset)'),
                dict(actor=actor['id'], search=search.strip() if search else None,
                     active=active_only, limit=limit, offset=offset))
            return {'items': [customer_row(row) for row in result.mappings().all()],
                    'limit': limit, 'offset': offset}
        except DBAPIError as exc:
            database_error(exc)

    @router.get('/{customer_id}')
    async def get_customer(customer_id: int = Path(gt=0, le=9223372036854775807),
                           actor=Depends(reader), session: AsyncSession = Depends(get_session)):
        try:
            result = await session.execute(text('CALL sp_get_customer(:actor,:id)'),
                                           {'actor': actor['id'], 'id': customer_id})
            row = result.mappings().first()
            if row is None:
                raise HTTPException(404, 'Không tìm thấy khách hàng trong phạm vi truy cập')
            return customer_row(row)
        except DBAPIError as exc:
            database_error(exc)

    @router.post('', status_code=201)
    async def create_customer(body: CustomerCreate, actor=Depends(writer),
                              session: AsyncSession = Depends(get_session)):
        if actor['role'] != 'ADMIN' and body.model_fields_set & {'user_id', 'sale_id'}:
            raise HTTPException(403, 'Chỉ ADMIN được liên kết tài khoản và phân công SALE')
        try:
            result = await session.execute(text(
                'CALL sp_create_customer(:actor,:name,:phone,:email,:address,:user_id,:sale_id)'),
                {'actor': actor['id'], **body.model_dump(mode='json')})
            row = customer_row(result.mappings().one())
            await session.commit()
            return row
        except DBAPIError as exc:
            await session.rollback()
            database_error(exc)

    @router.patch('/{customer_id}')
    async def update_customer(body: CustomerUpdate,
                              customer_id: int = Path(gt=0, le=9223372036854775807),
                              actor=Depends(writer), session: AsyncSession = Depends(get_session)):
        if actor['role'] != 'ADMIN' and body.model_fields_set & {'user_id', 'sale_id', 'is_active'}:
            raise HTTPException(403, 'Chỉ ADMIN được đổi liên kết, phân công và kích hoạt khách hàng')
        try:
            result = await session.execute(text('CALL sp_update_customer(:actor,:id,:patch)'),
                {'actor': actor['id'], 'id': customer_id,
                 'patch': body.model_dump_json(exclude_unset=True)})
            row = customer_row(result.mappings().one())
            await session.commit()
            return row
        except DBAPIError as exc:
            await session.rollback()
            database_error(exc)

    @router.delete('/{customer_id}', status_code=204)
    async def deactivate_customer(customer_id: int = Path(gt=0, le=9223372036854775807),
                                  actor=Depends(writer), session: AsyncSession = Depends(get_session)):
        try:
            await session.execute(text('CALL sp_deactivate_customer(:actor,:id)'),
                                  {'actor': actor['id'], 'id': customer_id})
            await session.commit()
            return Response(status_code=204)
        except DBAPIError as exc:
            await session.rollback()
            database_error(exc)

    return router
