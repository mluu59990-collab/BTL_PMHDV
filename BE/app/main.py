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
from fastapi import Query
from pydantic import ConfigDict, EmailStr, field_validator
from sqlalchemy.exc import IntegrityError
from typing import Literal
from pydantic import model_validator
from datetime import datetime, timezone
from decimal import Decimal
from pydantic import AwareDatetime
import json
from datetime import date
from zoneinfo import ZoneInfo



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




@app.get('/users')
async def get_users(user=Depends(require_roles('ADMIN')),
                    limit: int = Query(default=10, ge=1, le=100),
                    offset: int = Query(default=0, ge=0, le=2147483647),
                    session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_get_users_page(:limit,:offset)'),
                                   {'limit':limit,'offset':offset})
    return [dict(row) for row in result.mappings().all()]


# Đăng ký tài khoản công khai.


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




def serialize_row(row):
    # Giữ nguyên độ chính xác tiền tệ; timestamp lưu UTC trong MySQL.
    return {key: str(value) if isinstance(value, Decimal) else
            value.replace(tzinfo=timezone.utc).isoformat() if isinstance(value, datetime) else value
            for key,value in row.items()}


def normalize_currency(value):
    value = value.upper()
    return 'CNY' if value == 'NDT' else value


class ExchangeRateCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    currency_code: Literal['CNY','USD']
    rate: Decimal = Field(gt=0,max_digits=18,decimal_places=4,allow_inf_nan=False)
    note: str | None = Field(default=None,max_length=255)

    @field_validator('currency_code',mode='before')
    @classmethod
    def currency_alias(cls,value):
        return normalize_currency(value) if isinstance(value,str) else value


@app.post('/exchange-rates',status_code=201)
async def create_exchange_rate(body: ExchangeRateCreate, actor=Depends(require_roles('ADMIN')),
                               session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text('CALL sp_create_exchange_rate(:actor,:currency,:rate,:note)'),
            {'actor':actor['id'],'currency':body.currency_code,'rate':body.rate,'note':body.note})
        row = serialize_row(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        if exc.orig.args[0] == 1644:
            raise HTTPException(403,'Không có quyền cập nhật tỷ giá') from None
        raise
    return row


@app.get('/exchange-rates/current')
async def current_exchange_rates(user=Depends(current_user), session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_current_exchange_rates(:currency)'),{'currency':None})
    return [serialize_row(row) for row in result.mappings().all()]


@app.get('/exchange-rates/current/{currency}')
async def current_exchange_rate(currency: Literal['CNY','USD','NDT'], user=Depends(current_user),
                                session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_current_exchange_rates(:currency)'),
                                   {'currency':normalize_currency(currency)})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404,'Chưa cấu hình tỷ giá cho ngoại tệ này')
    return serialize_row(row)


@app.get('/exchange-rates/history')
async def exchange_rate_history(currency_code: Literal['CNY','USD','NDT'] | None = None,
                                date_from: AwareDatetime | None = None,
                                date_to: AwareDatetime | None = None,
                                limit: int = Query(default=20,ge=1,le=100),
                                offset: int = Query(default=0,ge=0,le=2147483647),
                                user=Depends(current_user),session: AsyncSession = Depends(get_session)):
    if date_from and date_to and date_from>date_to:
        raise HTTPException(422,'date_from không được sau date_to')
    result = await session.execute(text('CALL sp_exchange_rate_history(:currency,:start,:end,:limit,:offset)'),
        {'currency':normalize_currency(currency_code) if currency_code else None,
         'start':date_from.astimezone(timezone.utc).replace(tzinfo=None) if date_from else None,
         'end':date_to.astimezone(timezone.utc).replace(tzinfo=None) if date_to else None,
         'limit':limit,'offset':offset})
    return {'items':[serialize_row(row) for row in result.mappings().all()],'limit':limit,'offset':offset}



FeeUnit = Literal['PERCENT','VND','VND_PER_KG','VND_PER_M3','VND_PER_ITEM','VND_PER_PACKAGE']


def today_vn():
    return datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()


class FeeTier(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tier_min: Decimal = Field(default=Decimal('0'),ge=0,max_digits=18,decimal_places=4,allow_inf_nan=False)
    tier_max: Decimal | None = Field(default=None,gt=0,max_digits=18,decimal_places=4,allow_inf_nan=False)
    value: Decimal = Field(ge=0,max_digits=18,decimal_places=4,allow_inf_nan=False)

    @model_validator(mode='after')
    def valid_range(self):
        if self.tier_max is not None and self.tier_max<=self.tier_min:
            raise ValueError('tier_max phải lớn hơn tier_min')
        return self


class FeeConfigCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fee_type: str = Field(pattern=r'^[A-Z][A-Z0-9_]{1,49}$')
    description: str | None = Field(default=None,max_length=255)
    unit: FeeUnit
    effective_date: date = Field(default_factory=today_vn)
    tiers: list[FeeTier] = Field(min_length=1,max_length=100)

    @model_validator(mode='after')
    def validate_tiers(self):
        self.tiers.sort(key=lambda tier:tier.tier_min)
        for i,tier in enumerate(self.tiers):
            if self.unit=='PERCENT' and tier.value>100:
                raise ValueError('Phí phần trăm không được vượt quá 100')
            if i and (self.tiers[i-1].tier_max is None or self.tiers[i-1].tier_max>tier.tier_min):
                raise ValueError('Các bậc phí không được chồng lấn')
        return self


class FeeConfigUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str | None = Field(default=None,max_length=255)
    is_active: bool | None = None

    @model_validator(mode='after')
    def supplied_fields(self):
        if not self.model_fields_set or ('is_active' in self.model_fields_set and self.is_active is None):
            raise ValueError('Cần description hoặc is_active; is_active không được null')
        return self


def fee_row(row):
    data = serialize_row(row)
    data['tiers'] = json.loads(data['tiers']) if isinstance(data['tiers'],str) else data['tiers']
    data['tiers'].sort(key=lambda tier:Decimal(tier['tier_min']))
    data['is_active'] = bool(data['is_active'])
    return data


def fee_db_error(exc):
    if exc.orig.args[0] == 1644:
        message = str(exc.orig.args[1])
        if message == 'FORBIDDEN': raise HTTPException(403,'Không có quyền cấu hình phí') from None
        if message == 'NOT_FOUND': raise HTTPException(404,'Không tìm thấy bảng phí') from None
        raise HTTPException(422,'Bậc phí hoặc giá trị phí không hợp lệ') from None
    raise exc


@app.post('/fee-configs',status_code=201)
async def create_fee_config(body: FeeConfigCreate,actor=Depends(require_roles('ADMIN')),
                            session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text('CALL sp_create_fee_config(:actor,:type,:description,:unit,:date,:tiers)'),
            {'actor':actor['id'],'type':body.fee_type,'description':body.description,'unit':body.unit,
             'date':body.effective_date,'tiers':json.dumps([tier.model_dump(mode='json') for tier in body.tiers])})
        row = fee_row(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        fee_db_error(exc)
    return row


@app.get('/fee-configs')
async def list_fee_configs(fee_type: str | None = Query(default=None, max_length=50, pattern=r"^[A-Z][A-Z0-9_]{1,49}$"),active_only: bool = True,
                           limit: int = Query(default=20,ge=1,le=100),offset: int = Query(default=0,ge=0,le=2147483647),
                           user=Depends(current_user),session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_list_fee_configs(:type,:active,:limit,:offset)'),
        {'type':fee_type,'active':active_only,'limit':limit,'offset':offset})
    return {'items':[fee_row(row) for row in result.mappings().all()],'limit':limit,'offset':offset}


@app.get('/fee-configs/current')
async def current_fee_configs(fee_type: str | None = Query(default=None, max_length=50, pattern=r"^[A-Z][A-Z0-9_]{1,49}$"),unit: FeeUnit | None = None,on_date: date | None = None,
                              user=Depends(current_user),session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_current_fee_configs(:type,:unit,:date)'),
        {'type':fee_type,'unit':unit,'date':on_date or today_vn()})
    return [fee_row(row) for row in result.mappings().all()]


@app.get('/fee-configs/{config_id}')
async def get_fee_config(config_id: int,user=Depends(current_user),session: AsyncSession = Depends(get_session)):
    result = await session.execute(text('CALL sp_get_fee_config(:id)'),{'id':config_id})
    row = result.mappings().first()
    if row is None: raise HTTPException(404,'Không tìm thấy bảng phí')
    return fee_row(row)


@app.patch('/fee-configs/{config_id}')
async def update_fee_config(config_id: int,body: FeeConfigUpdate,actor=Depends(require_roles('ADMIN')),
                            session: AsyncSession = Depends(get_session)):
    try:
        result = await session.execute(text('CALL sp_update_fee_config(:actor,:id,:set_desc,:description,:active)'),
            {'actor':actor['id'],'id':config_id,'set_desc':'description' in body.model_fields_set,
             'description':body.description,'active':body.is_active})
        row = fee_row(result.mappings().one())
        await session.commit()
    except DBAPIError as exc:
        await session.rollback()
        fee_db_error(exc)
    return row


@app.delete('/fee-configs/{config_id}',status_code=204)
async def deactivate_fee_config(config_id: int,actor=Depends(require_roles('ADMIN')),
                                session: AsyncSession = Depends(get_session)):
    await update_fee_config(config_id,FeeConfigUpdate(is_active=False),actor,session)
    return Response(status_code=204)
