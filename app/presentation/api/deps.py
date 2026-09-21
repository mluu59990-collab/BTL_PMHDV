"""Dependency Injection: lắp repository + service cho từng request."""
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.auth_service import AuthService
from app.application.services.exchange_rate_service import ExchangeRateService
from app.application.services.fee_config_service import FeeConfigService
from app.application.services.user_service import UserService
from app.core.config import get_settings
from app.domain.entities import User
from app.domain.enums import RoleCode
from app.domain.exceptions import PermissionDeniedError
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.repositories.exchange_rate_repository import SqlExchangeRateRepository
from app.infrastructure.repositories.fee_config_repository import SqlFeeConfigRepository
from app.infrastructure.repositories.refresh_token_repository import SqlRefreshTokenRepository
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.infrastructure.security.jwt_provider import JwtTokenProvider
from app.infrastructure.security.password import Argon2PasswordHasher

settings = get_settings()

# Singleton dùng chung (không giữ state theo request)
password_hasher = Argon2PasswordHasher()
token_provider = JwtTokenProvider(
    secret=settings.jwt_secret_key,
    algorithm=settings.jwt_algorithm,
    access_minutes=settings.access_token_expire_minutes,
    refresh_days=settings.refresh_token_expire_days,
)

# Trỏ tới endpoint login để nút "Authorize" trong Swagger hoạt động
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/login")


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(
        users=SqlUserRepository(session),
        refresh_tokens=SqlRefreshTokenRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        hasher=password_hasher,
        tokens=token_provider,
    )


def get_user_service(session: AsyncSession = Depends(get_session)) -> UserService:
    return UserService(
        users=SqlUserRepository(session),
        refresh_tokens=SqlRefreshTokenRepository(session),
        uow=SqlAlchemyUnitOfWork(session),
        hasher=password_hasher,
    )


def get_exchange_rate_service(session: AsyncSession = Depends(get_session)) -> ExchangeRateService:
    return ExchangeRateService(rates=SqlExchangeRateRepository(session), uow=SqlAlchemyUnitOfWork(session))


def get_fee_config_service(session: AsyncSession = Depends(get_session)) -> FeeConfigService:
    return FeeConfigService(fees=SqlFeeConfigRepository(session), uow=SqlAlchemyUnitOfWork(session))


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    auth: AuthService = Depends(get_auth_service),
) -> User:
    return await auth.authenticate(token)


def require_roles(*allowed: RoleCode):
    """RBAC: chỉ cho các vai trò trong `allowed` đi qua. ADMIN luôn được phép (toàn quyền - SRS B.2.2).

        @router.get("/x", dependencies=[Depends(require_roles(RoleCode.SALE))])
        current: User = Depends(require_roles(RoleCode.WAREHOUSE))
    """

    async def checker(current: User = Depends(get_current_user)) -> User:
        if current.role != RoleCode.ADMIN and current.role not in allowed:
            raise PermissionDeniedError("Bạn không có quyền thực hiện thao tác này")
        return current

    return checker
