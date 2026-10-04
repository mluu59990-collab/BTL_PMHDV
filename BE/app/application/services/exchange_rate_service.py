from decimal import Decimal

from app.application.ports import UnitOfWork
from app.domain.entities import ExchangeRate
from app.domain.enums import CurrencyCode
from app.domain.exceptions import NotFoundError
from app.domain.repositories import ExchangeRateRepository


class ExchangeRateService:
    def __init__(self, rates: ExchangeRateRepository, uow: UnitOfWork):
        self._rates = rates
        self._uow = uow

    async def set_rate(
        self, *, currency: CurrencyCode, rate: Decimal, note: str | None, actor_id: int
    ) -> ExchangeRate:
        """Cập nhật tỷ giá = thêm 1 dòng mới; các dòng cũ giữ nguyên làm lịch sử (REQ-1.3)."""
        created = await self._rates.add(
            ExchangeRate(currency_code=currency.value, rate=rate, note=note, created_by=actor_id)
        )
        await self._uow.commit()
        return created

    async def get_current(self, currency: CurrencyCode) -> ExchangeRate:
        rate = await self._rates.get_latest(currency.value)
        if rate is None:
            raise NotFoundError(f"Chưa có tỷ giá cho {currency.value}")
        return rate

    async def get_current_all(self) -> list[ExchangeRate]:
        return await self._rates.list_latest_all()

    async def history(
        self, *, currency: CurrencyCode | None, offset: int, limit: int
    ) -> tuple[list[ExchangeRate], int]:
        return await self._rates.list_history(
            currency_code=currency.value if currency else None, offset=offset, limit=limit
        )
