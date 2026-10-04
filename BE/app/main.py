"""Backend logistics: truy cập dữ liệu qua stored procedure, nhận request từ gateway."""
from contextlib import asynccontextmanager
import secrets

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
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
    access = token_provider.create_access_token(user_id=user['id'], role=user['role'])
    return {'access_token': access.token, 'token_type': 'bearer',
            'expires_in': settings.access_token_expire_minutes * 60,
            'user': {key: user[key] for key in ('id', 'username', 'full_name', 'role')}}


@app.get('/auth/me')
async def me(user=Depends(current_user)):
    return dict(user)


@app.get('/users')
async def get_users(user=Depends(current_user), session: AsyncSession = Depends(get_session)):
    # Vai trò lấy từ DB hiện tại, không tin role do client gửi hoặc JWT cũ.
    if user['role'] != 'ADMIN':
        raise HTTPException(403, 'Chỉ ADMIN được xem danh sách người dùng')
    result = await session.execute(text('CALL sp_get_users()'))
    return [dict(row) for row in result.mappings().all()]
