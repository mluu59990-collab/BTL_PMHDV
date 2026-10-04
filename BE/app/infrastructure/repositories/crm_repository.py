from sqlalchemy import func, or_, select

from app.domain.crm_repository import CrmRepository
from app.infrastructure.db.crm_models import CustomerModel, VipMembershipModel
from app.infrastructure.repositories.catalog_repository import SqlCatalogRepository


class SqlCrmRepository(SqlCatalogRepository, CrmRepository):
    async def list(self, *, offset, limit, search=None, active_only=True, filters=None):
        conditions = [self.model.is_active.is_(True)] if active_only else []
        if search and self.search_fields:
            conditions.append(
                or_(
                    *[
                        getattr(self.model, key).icontains(search, autoescape=True)
                        for key in self.search_fields
                    ]
                )
            )
        for key, value in (filters or {}).items():
            if value is None:
                continue
            if key == "owner_sale_id":
                conditions.append(
                    self.model.customer_id.in_(
                        select(CustomerModel.id).where(CustomerModel.sale_id == value)
                    )
                )
            elif key == "date_from":
                conditions.append(self.model.shipped_on >= value)
            elif key == "date_to":
                conditions.append(self.model.shipped_on <= value)
            else:
                conditions.append(getattr(self.model, key) == value)
        total = (
            await self._s.execute(
                select(func.count()).select_from(self.model).where(*conditions)
            )
        ).scalar_one()
        rows = (
            (
                await self._s.execute(
                    select(self.model)
                    .where(*conditions)
                    .order_by(self.model.id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return [self._entity(row) for row in rows], total

    async def membership_overlaps(self, customer_id, start, end, exclude_id=None):
        model = VipMembershipModel
        query = select(model.id).where(
            model.customer_id == customer_id,
            model.is_active.is_(True),
            model.valid_from <= end,
            model.valid_until >= start,
        )
        if exclude_id is not None:
            query = query.where(model.id != exclude_id)
        return (await self._s.execute(query.limit(1))).scalar_one_or_none() is not None
