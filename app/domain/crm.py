"""CRM records for session 3 (REQ-2.1 through REQ-2.7)."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.catalog import CatalogRecord


@dataclass(kw_only=True)
class Customer(CatalogRecord):
    code: str
    name: str
    sale_id: int | None = None
    user_id: int | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    credit_limit: Decimal = Decimal(0)
    note: str | None = None


@dataclass(kw_only=True)
class CrmTracking(CatalogRecord):
    customer_id: int
    tracking_code: str
    shipped_on: date
    note: str | None = None


@dataclass(kw_only=True)
class CareTask(CatalogRecord):
    customer_id: int
    title: str
    due_on: date
    status: str = "NEW"
    note: str | None = None


@dataclass(kw_only=True)
class SalesPlan(CatalogRecord):
    sale_id: int
    period_start: date
    period_type: str
    target_amount: Decimal
    actual_amount: Decimal = Decimal(0)
    note: str | None = None


@dataclass(kw_only=True)
class ServiceReview(CatalogRecord):
    customer_id: int
    period_start: date
    period_end: date
    rating: int
    comment: str | None = None


@dataclass(kw_only=True)
class VipPackage(CatalogRecord):
    code: str
    name: str
    conditions: str
    benefits: str
    duration_days: int


@dataclass(kw_only=True)
class VipMembership(CatalogRecord):
    customer_id: int
    package_id: int
    valid_from: date
    valid_until: date
    note: str | None = None
