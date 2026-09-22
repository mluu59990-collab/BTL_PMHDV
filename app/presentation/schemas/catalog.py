from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    model_validator,
)

from app.domain.catalog import BrandRightType


def normalize_code(value):
    return value.strip().upper() if isinstance(value, str) else value


def http_url(value: str) -> str:
    return str(TypeAdapter(HttpUrl).validate_python(value))


def marketplace_url(value: str) -> str:
    host = urlsplit(value).hostname or ""
    if not any(
        host == domain or host.endswith("." + domain)
        for domain in ("1688.com", "taobao.com", "tmall.com")
    ):
        raise ValueError("Link sản phẩm phải thuộc 1688.com, taobao.com hoặc tmall.com")
    return value


Code = Annotated[
    str, Field(pattern=r"^[A-Z0-9][A-Z0-9_.-]{0,49}$"), BeforeValidator(normalize_code)
]
Name = Annotated[str, Field(min_length=1, max_length=150)]
LongName = Annotated[str, Field(min_length=1, max_length=255)]
Description = Annotated[str, Field(max_length=5000)]
Price = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
Id = Annotated[int, Field(gt=0, le=9223372036854775807)]
WebURL = Annotated[str, Field(max_length=2048), AfterValidator(http_url)]
SourceURL = Annotated[WebURL, AfterValidator(marketplace_url)]
Currency = Literal["CNY", "USD", "VND"]


class CatalogInput(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, use_enum_values=True
    )


class PatchInput(CatalogInput):
    non_nullable: ClassVar[set[str]] = {"is_active"}

    @model_validator(mode="after")
    def reject_null(self):
        for field in self.model_fields_set & self.non_nullable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} không được null")
        return self


class ReferenceCreate(CatalogInput):
    code: Code
    name: Name
    description: Description | None = None
    is_active: bool = True


class ReferenceUpdate(PatchInput):
    non_nullable = {"code", "name", "is_active"}
    code: Code | None = None
    name: Name | None = None
    description: Description | None = None
    is_active: bool | None = None


class RecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReferenceRead(RecordRead):
    code: str
    name: str
    description: str | None


class ProductCreate(CatalogInput):
    sku: Code
    name: LongName
    reference_price: Price
    currency_code: Currency = "CNY"
    source_url: SourceURL | None = None
    image_url: WebURL | None = None
    description: Description | None = None
    origin_country_id: Id | None = None
    shipping_country_id: Id | None = None
    unit_id: Id | None = None
    package_type_id: Id | None = None
    category_id: Id | None = None
    is_active: bool = True


class ProductUpdate(PatchInput):
    non_nullable = {"sku", "name", "reference_price", "currency_code", "is_active"}
    sku: Code | None = None
    name: LongName | None = None
    reference_price: Price | None = None
    currency_code: Currency | None = None
    source_url: SourceURL | None = None
    image_url: WebURL | None = None
    description: Description | None = None
    origin_country_id: Id | None = None
    shipping_country_id: Id | None = None
    unit_id: Id | None = None
    package_type_id: Id | None = None
    category_id: Id | None = None
    is_active: bool | None = None


class ProductRead(RecordRead):
    sku: str
    name: str
    reference_price: Decimal
    currency_code: str
    source_url: str | None
    image_url: str | None
    description: str | None
    origin_country_id: int | None
    shipping_country_id: int | None
    unit_id: int | None
    package_type_id: int | None
    category_id: int | None


class BrandRightCreate(CatalogInput):
    brand_name: Name
    holder_name: LongName
    right_type: BrandRightType
    product_id: Id | None = None
    category_id: Id | None = None
    document_url: WebURL | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    note: Description | None = None
    is_active: bool = True


class BrandRightUpdate(PatchInput):
    non_nullable = {"brand_name", "holder_name", "right_type", "is_active"}
    brand_name: Name | None = None
    holder_name: LongName | None = None
    right_type: BrandRightType | None = None
    product_id: Id | None = None
    category_id: Id | None = None
    document_url: WebURL | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    note: Description | None = None
    is_active: bool | None = None


class BrandRightRead(RecordRead):
    brand_name: str
    holder_name: str
    right_type: BrandRightType
    product_id: int | None
    category_id: int | None
    document_url: str | None
    valid_from: date | None
    valid_until: date | None
    note: str | None
