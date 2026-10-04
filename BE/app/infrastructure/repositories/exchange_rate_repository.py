from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import ExchangeRate
from app.domain.repositories import ExchangeRateRepository
from app.infrastructure.db.models import ExchangeRateModel as M
from app.infrastructure.db.unit_of_work import flush_or_conflict


def _to_entity(m: M) -> ExchangeRate:
    return ExchangeRate(
        id=m.id,
        currency_code=m.currency_code,
        rate=m.rate,
        note=m.note,
        created_by=m.created_by,
        created_at=m.created_at,
    )


class SqlExchangeRateRepository(ExchangeRateRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, rate: ExchangeRate) -> ExchangeRate:
        m = M(currency_code=rate.currency_code, rate=rate.rate, note=rate.note, created_by=rate.created_by)
        self._s.add(m)
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def get_latest(self, currency_code: str) -> ExchangeRate | None:
        stmt = (
            select(M)
            .where(M.currency_code == currency_code)
            .order_by(M.created_at.desc(), M.id.desc())
            .limit(1)
        )
        m = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def list_latest_all(self) -> list[ExchangeRate]:
        ranked = select(M.id, func.row_number().over(
            partition_by=M.currency_code,
            order_by=(M.created_at.desc(), M.id.desc()),
        ).label("position")).subquery()
        stmt = select(M).join(ranked, M.id == ranked.c.id).where(ranked.c.position == 1).order_by(M.currency_code)
        return [_to_entity(m) for m in (await self._s.execute(stmt)).scalars().all()]

    async def list_history(
        self, *, currency_code: str | None, offset: int, limit: int
    ) -> tuple[list[ExchangeRate], int]:
        conds = [M.currency_code == currency_code] if currency_code else []
        total = (await self._s.execute(select(func.count()).select_from(M).where(*conds))).scalar_one()
        stmt = select(M).where(*conds).order_by(M.created_at.desc(), M.id.desc()).offset(offset).limit(limit)
        return [_to_entity(m) for m in (await self._s.execute(stmt)).scalars().all()], total
