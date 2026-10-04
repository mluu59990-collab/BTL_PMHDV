"""Backend logistics: truy cập dữ liệu qua stored procedure, nhận request từ gateway."""
from contextlib import asynccontextmanager
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import DBAPIError
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.enums import TokenType
from app.domain.exceptions import AuthenticationError
from app.infrastructure.db.session import engine, get_session
from app.infrastructure.security.jwt_provider import JwtTokenProvider
from app.infrastructure.security.password import Argon2PasswordHasher

settings = get_settings()
password_hasher = Argon2PasswordHasher()
token_provider = JwtTokenProvider(
    secret=settings.jwt_secret_key, algorithm=settings.jwt_algorithm,
    access_minutes=settings.access_token_expire_minutes,
    refresh_days=settings.refresh_token_expire_days,
)
# Làm kiểm tra hash cho cả username không tồn tại để giảm khác biệt thời gian.
DUMMY_HASH = '$argon2id$v=19$m=65536,t=3,p=4$PAegmon5+AXpIt3dQSt6gA$rGVcJZERkqmKQVdTtKwz+IEY3AiIBU30VbCI0U21Dvc'


@asynccontextmanager
async def lifespan(app):
    yield
    await engine.dispose()


app = FastAPI(title='Logistics Backend', lifespan=lifespan,
              docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware('http')
async def require_gateway(request: Request, call_next):
    keys = request.headers.getlist('x-gateway-key')
    if len(keys) != 1 or not secrets.compare_digest(
            keys[0].encode(), settings.gateway_shared_secret.encode()):
        return JSONResponse(status_code=403, content={'detail': 'Chỉ nhận request qua gateway'})
    return await call_next(request)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


async def current_user(request: Request, session: AsyncSession = Depends(get_session)):
    scheme, _, token = request.headers.get('authorization', '').partition(' ')
    try:
        if scheme.lower() != 'bearer' or not token:
            raise AuthenticationError('Thiếu token')
        payload = token_provider.decode(token, expected_type=TokenType.ACCESS)
    except AuthenticationError:
        raise HTTPException(401, 'Token không hợp lệ hoặc đã hết hạn',
                            headers={'WWW-Authenticate': 'Bearer'}) from None
    result = await session.execute(text('CALL sp_get_auth_user(:user_id)'),
                                   {'user_id': payload.user_id})
    user = result.mappings().first()
    if user is None or user['status'] != 'ACTIVE':
        raise HTTPException(403, 'Tài khoản không hoạt động')
    return user


@app.get('/health')
async def health(session: AsyncSession = Depends(get_session)):
    await session.execute(text('CALL sp_health()'))
    return {'status': 'ok', 'database': 'ok'}


@app.post('/auth/login')
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_get_user_for_login(:username)'),
                                   {'username': body.username})
    user = result.mappings().first()
    valid = await password_hasher.verify(body.password, user['password_hash'] if user else DUMMY_HASH)
    if user is None or not valid:
        raise HTTPException(401, 'Sai tên đăng nhập hoặc mật khẩu')
    if user['status'] != 'ACTIVE':
        raise HTTPException(403, 'Tài khoản không hoạt động')
    refresh = token_provider.create_refresh_token(user_id=user['id'])
    try:
        result = await session.execute(text('CALL sp_create_session(:user_id,:jti,:expires)'),
            {'user_id':user['id'],'jti':refresh.jti,'expires':refresh.expires_at.replace(tzinfo=None)})
        user = dict(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        if exc.orig.args[0] == 1644:
            raise HTTPException(403, 'Tài khoản không hoạt động') from None
        raise
    return token_response(user, refresh)



@app.get('/auth/me')
async def me(user=Depends(current_user)):
    return dict(user)


def require_roles(*roles):
    async def check_role(user=Depends(current_user)):
        if user['role'] not in roles:
            raise HTTPException(403, 'Không có quyền thực hiện chức năng này')
        return user
    return check_role


from fastapi import Query


@app.get('/users')
async def get_users(user=Depends(require_roles('ADMIN')),
                    limit: int = Query(default=10, ge=1, le=100),
                    offset: int = Query(default=0, ge=0),
                    session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_get_users_page(:limit,:offset)'),
                                   {'limit':limit,'offset':offset})
    return [dict(row) for row in result.mappings().all()]


# Đăng ký tài khoản công khai.
from pydantic import ConfigDict, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    username: str = Field(pattern=r'^[A-Za-z0-9_.-]{3,50}$')
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r'^\+?[0-9]{8,15}$')

    @field_validator('full_name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('Họ tên không được để trống')
        return value.strip()


@app.post('/auth/register', status_code=201)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_session)):
    hashed = await password_hasher.hash(body.password)
    try:
        result = await session.execute(text('CALL sp_register_user(:username,:email,:full_name,:phone,:password_hash)'),
            {'username':body.username,'email':str(body.email) if body.email else None,
             'full_name':body.full_name,'phone':body.phone,'password_hash':hashed})
        user = dict(result.mappings().one())
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if exc.orig.args[0] == 1062:
            raise HTTPException(409, 'Tên đăng nhập hoặc email đã tồn tại') from None
        raise
    return user


def token_response(user, refresh):
    access = token_provider.create_access_token(user_id=user['id'], role=user['role'])
    return {'access_token':access.token, 'refresh_token':refresh.token, 'token_type':'bearer',
            'expires_in':settings.access_token_expire_minutes*60,
            'user':{key:user[key] for key in ('id','username','full_name','role')}}


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: str = Field(min_length=1, max_length=4096)


@app.post('/auth/refresh')
async def refresh_session(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    try:
        payload = token_provider.decode(body.refresh_token, expected_type=TokenType.REFRESH)
    except AuthenticationError:
        raise HTTPException(401, 'Refresh token không hợp lệ hoặc đã hết hạn') from None
    new_token = token_provider.create_refresh_token(user_id=payload.user_id)
    try:
        result = await session.execute(text('CALL sp_rotate_refresh(:user_id,:old_jti,:new_jti,:expires)'),
            {'user_id':payload.user_id,'old_jti':payload.jti,'new_jti':new_token.jti,
             'expires':new_token.expires_at.replace(tzinfo=None)})
        user = dict(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        if exc.orig.args[0] == 1644:
            raise HTTPException(401, 'Refresh token không còn hiệu lực') from None
        raise
    return token_response(user, new_token)


@app.post('/auth/logout', status_code=204)
async def logout(body: RefreshRequest, session: AsyncSession = Depends(get_session)):
    try:
        payload = token_provider.decode(body.refresh_token, expected_type=TokenType.REFRESH)
    except AuthenticationError:
        return Response(status_code=204)
    await session.execute(text('CALL sp_logout_session(:user_id,:jti)'),
                          {'user_id':payload.user_id,'jti':payload.jti})
    await session.commit()
    return Response(status_code=204)


from typing import Literal
from pydantic import model_validator

Role = Literal['ADMIN','SALE','WAREHOUSE','ACCOUNTANT','CUSTOMER']
UserStatus = Literal['ACTIVE','INACTIVE','LOCKED']


class UserAccessUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: Role | None = None
    status: UserStatus | None = None

    @model_validator(mode='after')
    def at_least_one(self):
        if self.role is None and self.status is None:
            raise ValueError('Cần role hoặc status')
        return self


@app.get('/auth/permissions')
async def permissions(user=Depends(current_user)):
    allowed = ['profile:read','exchange-rates:read','fee-configs:read']
    if user['role'] == 'ADMIN':
        allowed += ['users:read','users:manage','exchange-rates:write','fee-configs:write']
    return {'role':user['role'],'permissions':allowed}


@app.patch('/users/{user_id}/access')
async def update_user_access(user_id: int, body: UserAccessUpdate,
                             actor=Depends(require_roles('ADMIN')),
                             session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text('CALL sp_update_user_access(:actor,:id,:role,:status)'),
            {'actor':actor['id'],'id':user_id,'role':body.role,'status':body.status})
        user = dict(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        if exc.orig.args[0] == 1644:
            message = str(exc.orig.args[1])
            status,detail = {'NOT_FOUND':(404,'Không tìm thấy tài khoản'),
                            'LAST_ADMIN':(409,'Phải giữ ít nhất một ADMIN đang hoạt động'),
                            'FORBIDDEN':(403,'Không có quyền quản lý tài khoản')}.get(message,(409,'Không thể cập nhật tài khoản'))
            raise HTTPException(status, detail) from None
        raise
    return user
