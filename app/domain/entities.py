"""Entity thuần Python - không phụ thuộc FastAPI/SQLAlchemy."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.domain.enums import RoleCode, UserStatus


@dataclass
class User:
    username: str
    full_name: str
    password_hash: str
    role: RoleCode
    email: str | None = None
    phone: str | None = None
    balance: Decimal = Decimal("0")
    status: UserStatus = UserStatus.ACTIVE
    id: int | None = None
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE


@dataclass
class RefreshToken:
    user_id: int
    jti: str
    expires_at: datetime
    id: int | None = None
    revoked_at: datetime | None = None
    created_at: datetime | None = None


@dataclass
class ExchangeRate:
    currency_code: str
    rate: Decimal
    note: str | None = None
    created_by: int | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class FeeConfig:
    fee_type: str
    value: Decimal
    unit: str
    description: str | None = None
    tier_min: Decimal | None = None
    tier_max: Decimal | None = None
    effective_date: date | None = None
    is_active: bool = True
    created_by: int | None = None
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
