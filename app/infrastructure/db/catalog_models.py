"""Ánh xạ sql/04_catalog_schema.sql; SQL là nguồn schema triển khai."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import utcnow
from app.infrastructure.db.models import Base


class CatalogMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )


class ReferenceMixin(CatalogMixin):
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)


class CountryModel(ReferenceMixin, Base):
    __tablename__ = "countries"


class UnitModel(ReferenceMixin, Base):
    __tablename__ = "units"


class PackageTypeModel(ReferenceMixin, Base):
    __tablename__ = "package_types"


class CategoryModel(ReferenceMixin, Base):
    __tablename__ = "categories"


class ProductModel(CatalogMixin, Base):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    reference_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency_code: Mapped[str] = mapped_column(String(3), default="CNY")
    source_url: Mapped[str | None] = mapped_column(String(2048))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    origin_country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"))
    shipping_country_id: Mapped[int | None] = mapped_column(ForeignKey("countries.id"))
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    package_type_id: Mapped[int | None] = mapped_column(ForeignKey("package_types.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))


class BrandRightModel(CatalogMixin, Base):
    __tablename__ = "brand_rights"

    brand_name: Mapped[str] = mapped_column(String(150))
    holder_name: Mapped[str] = mapped_column(String(255))
    right_type: Mapped[str] = mapped_column(String(30))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    document_url: Mapped[str | None] = mapped_column(String(2048))
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
