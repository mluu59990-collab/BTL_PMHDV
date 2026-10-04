from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.domain.entities import FeeConfig
from app.domain.repositories import FeeConfigRepository
from app.infrastructure.db.models import FeeConfigModel as M
from app.infrastructure.db.unit_of_work import flush_or_conflict


def _to_entity(m: M) -> FeeConfig:
    return FeeConfig(
        id=m.id,
        fee_type=m.fee_type,
        description=m.description,
        value=m.value,
        unit=m.unit,
        tier_min=m.tier_min,
        tier_max=m.tier_max,
        effective_date=m.effective_date,
        is_active=m.is_active,
        created_by=m.created_by,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class SqlFeeConfigRepository(FeeConfigRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, fee: FeeConfig) -> FeeConfig:
        m = M(
            fee_type=fee.fee_type,
            description=fee.description,
            value=fee.value,
            unit=fee.unit,
            tier_min=fee.tier_min,
            tier_max=fee.tier_max,
            effective_date=fee.effective_date,
            is_active=fee.is_active,
            created_by=fee.created_by,
        )
        self._s.add(m)
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def get_by_id(self, fee_id: int) -> FeeConfig | None:
        m = await self._s.get(M, fee_id)
        return _to_entity(m) if m else None

    async def update(self, fee: FeeConfig) -> FeeConfig:
        m = await self._s.get(M, fee.id)
        m.description = fee.description
        m.value = fee.value
        m.unit = fee.unit
        m.tier_min = fee.tier_min
        m.tier_max = fee.tier_max
        m.effective_date = fee.effective_date
        m.is_active = fee.is_active
        m.updated_at = utcnow()
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def list_fees(self, *, fee_type: str | None, active_only: bool) -> list[FeeConfig]:
        stmt = select(M)
        if fee_type:
            stmt = stmt.where(M.fee_type == fee_type)
        if active_only:
            stmt = stmt.where(M.is_active.is_(True))
        stmt = stmt.order_by(M.fee_type, M.unit, M.tier_min.asc(), M.effective_date.desc(), M.id)
        return [_to_entity(m) for m in (await self._s.execute(stmt)).scalars().all()]

    async def list_current(self, *, on_date: date, fee_type: str | None) -> list[FeeConfig]:
        ranked = select(M.id, func.row_number().over(
            partition_by=(M.fee_type, M.unit, M.tier_min),
            order_by=(M.effective_date.desc(), M.id.desc()),
        ).label("position")).where(M.is_active.is_(True), M.effective_date <= on_date)
        if fee_type:
            ranked = ranked.where(M.fee_type == fee_type)
        ranked = ranked.subquery()
        stmt = select(M).join(ranked, M.id == ranked.c.id).where(ranked.c.position == 1).order_by(M.fee_type, M.unit, M.tier_min.asc())
        return [_to_entity(m) for m in (await self._s.execute(stmt)).scalars().all()]
