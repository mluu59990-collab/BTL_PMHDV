from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import CurrencyCode


class ExchangeRateCreate(BaseModel):
    currency_code: CurrencyCode = Field(description="CNY (NDT) hoặc USD")
    rate: Decimal = Field(gt=0, max_digits=18, decimal_places=4, description="Số VNĐ cho 1 đơn vị ngoại tệ")
    note: str | None = Field(default=None, max_length=255)


class ExchangeRateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    currency_code: str
    rate: Decimal
    note: str | None
    created_by: int | None
    created_at: datetime
