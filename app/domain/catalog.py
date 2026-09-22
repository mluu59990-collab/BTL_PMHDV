"""Danh mục sản phẩm và quyền thương hiệu (REQ-3.1 đến REQ-3.6)."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class ReferenceKind(str, Enum):
    COUNTRIES = "countries"
    UNITS = "units"
    PACKAGE_TYPES = "package-types"
    CATEGORIES = "categories"


class BrandRightType(str, Enum):
    COPYRIGHT = "COPYRIGHT"
    DISTRIBUTION_AUTHORIZATION = "DISTRIBUTION_AUTHORIZATION"


@dataclass(kw_only=True)
class CatalogRecord:
    id: int | None = None
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(kw_only=True)
class ReferenceItem(CatalogRecord):
    code: str
    name: str
    description: str | None = None


@dataclass(kw_only=True)
class Product(CatalogRecord):
    sku: str
    name: str
    reference_price: Decimal
    currency_code: str = "CNY"
    source_url: str | None = None
    image_url: str | None = None
    description: str | None = None
    origin_country_id: int | None = None
    shipping_country_id: int | None = None
    unit_id: int | None = None
    package_type_id: int | None = None
    category_id: int | None = None


@dataclass(kw_only=True)
class BrandRight(CatalogRecord):
    brand_name: str
    holder_name: str
    right_type: str
    product_id: int | None = None
    category_id: int | None = None
    document_url: str | None = None
    valid_from: date | None = None
    valid_until: date | None = None
    note: str | None = None
