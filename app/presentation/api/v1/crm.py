from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.crm_service import CrmService
from app.domain import crm as entities
from app.domain.entities import User
from app.domain.enums import RoleCode
from app.domain.exceptions import BusinessRuleError
from app.infrastructure.db import crm_models as models
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.repositories.crm_repository import SqlCrmRepository
from app.infrastructure.repositories.user_repository import SqlUserRepository
from app.presentation.api.deps import require_roles
from app.presentation.api.v1.catalog import FilterId, Paging, RecordId
from app.presentation.schemas import crm as schemas
from app.presentation.schemas.common import Page

router = APIRouter(prefix="/crm", tags=["CRM — Buổi 3"])
Actor = Annotated[User, Depends(require_roles(RoleCode.SALE))]
Session = Annotated[AsyncSession, Depends(get_session)]

RESOURCES = [
    ("customers", entities.Customer, ("code", "name", "phone", "email")),
    ("trackings", entities.CrmTracking, ("tracking_code",)),
    ("care-tasks", entities.CareTask, ("title", "note")),
    ("sales-plans", entities.SalesPlan, ("note",)),
    ("service-reviews", entities.ServiceReview, ("comment",)),
    ("vip-packages", entities.VipPackage, ("code", "name")),
    ("vip-memberships", entities.VipMembership, ("note",)),
]


def mount(path, entity, search_fields):
    create_schema = getattr(schemas, entity.__name__ + "Create")
    update_schema = schemas.patch_schema(create_schema)
    read_schema = schemas.read_schema(create_schema)

    def service(session: Session, actor: Actor):
        def repo(cls, fields=()):
            return SqlCrmRepository(
                session, getattr(models, cls.__name__ + "Model"), cls, fields
            )

        return CrmService(
            repo(entity, search_fields),
            entity,
            repo(entities.Customer),
            repo(entities.VipPackage),
            SqlUserRepository(session),
            SqlAlchemyUnitOfWork(session),
            actor,
        )

    Service = Annotated[CrmService, Depends(service)]

    async def listing(
        service: Service,
        paging: Paging,
        customer_id: FilterId = None,
        sale_id: FilterId = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        filters = {}
        if customer_id is not None:
            if entity in (entities.Customer, entities.SalesPlan, entities.VipPackage):
                raise BusinessRuleError(
                    "Bộ lọc customer_id không áp dụng cho tài nguyên này"
                )
            filters["customer_id"] = customer_id
        if sale_id is not None:
            if entity == entities.VipPackage:
                raise BusinessRuleError("Bộ lọc sale_id không áp dụng cho gói VIP")
            filters[
                "sale_id"
                if entity in (entities.Customer, entities.SalesPlan)
                else "owner_sale_id"
            ] = sale_id
        if date_from or date_to:
            if entity != entities.CrmTracking:
                raise BusinessRuleError("Bộ lọc ngày chỉ áp dụng cho vận đơn")
            filters.update(date_from=date_from, date_to=date_to)
        items, total = await service.list(filters=filters, **paging.options)
        return Page[read_schema](
            items=[read_schema.model_validate(item) for item in items],
            total=total,
            offset=paging.options["offset"],
            limit=paging.options["limit"],
        )

    async def retrieve(record_id: RecordId, service: Service):
        return await service.get(record_id)

    async def create(body: create_schema, service: Service):
        return await service.create(body.model_dump())

    async def update(record_id: RecordId, body: update_schema, service: Service):
        return await service.update(record_id, body.model_dump(exclude_unset=True))

    async def delete(record_id: RecordId, service: Service):
        await service.deactivate(record_id)
        return Response(status_code=204)

    for suffix, method, endpoint, response, status in [
        ("", "GET", listing, Page[read_schema], 200),
        ("", "POST", create, read_schema, 201),
        ("/{record_id}", "GET", retrieve, read_schema, 200),
        ("/{record_id}", "PATCH", update, read_schema, 200),
        ("/{record_id}", "DELETE", delete, None, 204),
    ]:
        router.add_api_route(
            "/" + path + suffix,
            endpoint,
            methods=[method],
            response_model=response,
            status_code=status,
            name=method.lower() + "_" + path.replace("-", "_"),
        )


for resource in RESOURCES:
    mount(*resource)
