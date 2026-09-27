from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import EmailStr, Field, create_model

from app.presentation.schemas.catalog import (
    CatalogInput,
    Code,
    Description,
    Id,
    Name,
    PatchInput,
    RecordRead,
)

Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]


class CustomerCreate(CatalogInput):
    code: Code
    name: Name
    sale_id: Id | None = None
    user_id: Id | None = None
    phone: Annotated[str, Field(pattern=r"^\+?[0-9]{8,15}$")] | None = None
    email: EmailStr | None = None
    address: Description | None = None
    credit_limit: Money = Decimal(0)
    note: Description | None = None
    is_active: bool = True


class CrmTrackingCreate(CatalogInput):
    customer_id: Id
    tracking_code: Code
    shipped_on: date
    note: Description | None = None
    is_active: bool = True


class CareTaskCreate(CatalogInput):
    customer_id: Id
    title: Name
    due_on: date
    status: Literal["NEW", "CONTACTED", "FOLLOW_UP", "COMPLETED", "CANCELLED"] = "NEW"
    note: Description | None = None
    is_active: bool = True


class SalesPlanCreate(CatalogInput):
    sale_id: Id
    period_start: date
    period_type: Literal["MONTH", "QUARTER"]
    target_amount: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
    actual_amount: Money = Decimal(0)
    note: Description | None = None
    is_active: bool = True


class ServiceReviewCreate(CatalogInput):
    customer_id: Id
    period_start: date
    period_end: date
    rating: Annotated[int, Field(ge=1, le=5)]
    comment: Description | None = None
    is_active: bool = True


class VipPackageCreate(CatalogInput):
    code: Code
    name: Name
    conditions: Annotated[str, Field(min_length=1, max_length=5000)]
    benefits: Annotated[str, Field(min_length=1, max_length=5000)]
    duration_days: Annotated[int, Field(ge=1, le=3650)]
    is_active: bool = True


class VipMembershipCreate(CatalogInput):
    customer_id: Id
    package_id: Id
    valid_from: date
    valid_until: date
    note: Description | None = None
    is_active: bool = True


def patch_schema(schema):
    """Keep field constraints on partial updates; reject explicit null for required fields."""
    model = create_model(
        schema.__name__.replace("Create", "Update"),
        __base__=PatchInput,
        **{
            name: (Annotated[field.annotation, *field.metadata] | None, None)
            if field.metadata
            else (field.annotation | None, None)
            for name, field in schema.model_fields.items()
        },
    )
    model.non_nullable = {
        name
        for name, field in schema.model_fields.items()
        if type(None) not in getattr(field.annotation, "__args__", ())
    }
    return model


def read_schema(schema):
    return create_model(
        schema.__name__.replace("Create", "Read"), __base__=(schema, RecordRead)
    )
