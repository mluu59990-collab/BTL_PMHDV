from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.domain.enums import RoleCode, UserStatus

USERNAME_PATTERN = r"^[a-zA-Z0-9_.]{3,50}$"
PHONE_PATTERN = r"^\+?[0-9 .\-]{8,20}$"


class RegisterRequest(BaseModel):
    username: str = Field(pattern=USERNAME_PATTERN, description="3-50 ký tự: chữ, số, _ hoặc .")
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class AdminUserCreate(RegisterRequest):
    role: RoleCode


class UserUpdateMe(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=PHONE_PATTERN)


class AdminUserUpdate(UserUpdateMe):
    role: RoleCode | None = None
    status: UserStatus | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None
    full_name: str
    phone: str | None
    role: RoleCode
    balance: Decimal
    status: UserStatus
    last_login_at: datetime | None
    created_at: datetime
