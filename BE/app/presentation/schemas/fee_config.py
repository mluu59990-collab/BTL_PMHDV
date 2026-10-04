from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FeeUnit

FEE_TYPE_PATTERN = r"^[A-Z][A-Z0-9_]{1,49}$"


class FeeConfigCreate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    fee_type: str = Field(pattern=FEE_TYPE_PATTERN, examples=["PURCHASE_SERVICE_FEE"])
    description: str | None = Field(default=None, max_length=255)
    value: Decimal = Field(ge=0, max_digits=18, decimal_places=4)
    unit: FeeUnit
    tier_min: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    tier_max: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    effective_date: date | None = Field(default=None, description="Mặc định là hôm nay")
    is_active: bool = True


class FeeConfigUpdate(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    description: str | None = Field(default=None, max_length=255)
    value: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    unit: FeeUnit | None = None
    tier_min: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    tier_max: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=4)
    effective_date: date | None = None
    is_active: bool | None = None


class FeeConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fee_type: str
    description: str | None
    value: Decimal
    unit: str
    tier_min: Decimal | None
    tier_max: Decimal | None
    effective_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime
