"""Mapping for sql/06_crm_schema.sql."""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.catalog_models import CatalogMixin
from app.infrastructure.db.models import Base


class CustomerModel(CatalogMixin, Base):
    __tablename__ = "customers"
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    sale_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    credit_limit: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    note: Mapped[str | None] = mapped_column(Text)


class CrmTrackingModel(CatalogMixin, Base):
    __tablename__ = "crm_trackings"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    tracking_code: Mapped[str] = mapped_column(String(50))
    shipped_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)


class CareTaskModel(CatalogMixin, Base):
    __tablename__ = "care_tasks"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    title: Mapped[str] = mapped_column(String(150))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text)


class SalesPlanModel(CatalogMixin, Base):
    __tablename__ = "sales_plans"
    sale_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(10))
    target_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    actual_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    note: Mapped[str | None] = mapped_column(Text)


class ServiceReviewModel(CatalogMixin, Base):
    __tablename__ = "service_reviews"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)


class VipPackageModel(CatalogMixin, Base):
    __tablename__ = "vip_packages"
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(150))
    conditions: Mapped[str] = mapped_column(Text)
    benefits: Mapped[str] = mapped_column(Text)
    duration_days: Mapped[int] = mapped_column(Integer)


class VipMembershipModel(CatalogMixin, Base):
    __tablename__ = "vip_memberships"
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"))
    package_id: Mapped[int] = mapped_column(ForeignKey("vip_packages.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
