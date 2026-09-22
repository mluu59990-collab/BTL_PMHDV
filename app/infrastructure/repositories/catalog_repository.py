from dataclasses import asdict, fields
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.domain.catalog import BrandRight, Product, ReferenceItem, ReferenceKind
from app.domain.catalog_repository import CatalogRepository, T
from app.domain.exceptions import NotFoundError
from app.infrastructure.db.catalog_models import (
    BrandRightModel,
    CategoryModel,
    CountryModel,
    PackageTypeModel,
    ProductModel,
    UnitModel,
)
from app.infrastructure.db.unit_of_work import flush_or_conflict

REFERENCE_MODELS = {
    ReferenceKind.COUNTRIES: CountryModel,
    ReferenceKind.UNITS: UnitModel,
    ReferenceKind.PACKAGE_TYPES: PackageTypeModel,
    ReferenceKind.CATEGORIES: CategoryModel,
}


class SqlCatalogRepository(CatalogRepository[T]):
    def __init__(
        self,
        session: AsyncSession,
        model,
        entity: type[T],
        search_fields: tuple[str, ...],
    ):
        self._s = session
        self.model = model
        self.entity = entity
        self.search_fields = search_fields

    def _entity(self, model) -> T:
        return self.entity(
            **{f.name: getattr(model, f.name) for f in fields(self.entity)}
        )

    async def get(self, record_id: int, *, for_update: bool = False) -> T | None:
        stmt = select(self.model).where(self.model.id == record_id)
        if for_update:
            stmt = stmt.with_for_update().execution_options(populate_existing=True)
        model = (await self._s.execute(stmt)).scalar_one_or_none()
        return self._entity(model) if model else None

    async def add(self, record: T) -> T:
        data = asdict(record)
        for field in ("id", "created_at", "updated_at"):
            data.pop(field)
        model = self.model(**data)
        self._s.add(model)
        await flush_or_conflict(self._s)
        return self._entity(model)

    async def update(self, record_id: int, changes: dict[str, Any]) -> T:
        model = await self._s.get(self.model, record_id)
        if model is None:
            raise NotFoundError("Không tìm thấy bản ghi danh mục")
        for key, value in changes.items():
            setattr(model, key, value)
        model.updated_at = utcnow()
        await flush_or_conflict(self._s)
        return self._entity(model)

    async def list(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        active_only: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[T], int]:
        conditions = [self.model.is_active.is_(True)] if active_only else []
        if search:
            conditions.append(
                or_(
                    *(
                        getattr(self.model, name).icontains(search, autoescape=True)
                        for name in self.search_fields
                    )
                )
            )
        for key, value in (filters or {}).items():
            if value is not None:
                conditions.append(getattr(self.model, key) == value)
        count = (
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
        return [self._entity(row) for row in rows], count


def reference_repository(
    session: AsyncSession, kind: ReferenceKind
) -> SqlCatalogRepository[ReferenceItem]:
    return SqlCatalogRepository(
        session, REFERENCE_MODELS[kind], ReferenceItem, ("code", "name")
    )


def product_repository(session: AsyncSession) -> SqlCatalogRepository[Product]:
    return SqlCatalogRepository(session, ProductModel, Product, ("sku", "name"))


def brand_right_repository(session: AsyncSession) -> SqlCatalogRepository[BrandRight]:
    return SqlCatalogRepository(
        session, BrandRightModel, BrandRight, ("brand_name", "holder_name")
    )
