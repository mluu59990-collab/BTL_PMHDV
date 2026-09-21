from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Any

from app.application.ports import UnitOfWork
from app.core.clock import today_vn
from app.domain.entities import FeeConfig
from app.domain.exceptions import BusinessRuleError, NotFoundError
from app.domain.repositories import FeeConfigRepository

_EDITABLE = {"description", "value", "unit", "tier_min", "tier_max", "effective_date", "is_active"}


class FeeConfigService:
    def __init__(self, fees: FeeConfigRepository, uow: UnitOfWork):
        self._fees = fees
        self._uow = uow

    async def create(self, fee: FeeConfig, *, actor_id: int) -> FeeConfig:
        fee.created_by = actor_id
        if fee.effective_date is None:
            fee.effective_date = today_vn()
        self._validate(fee)
        created = await self._fees.add(fee)
        await self._uow.commit()
        return created

    async def get(self, fee_id: int) -> FeeConfig:
        fee = await self._fees.get_by_id(fee_id)
        if fee is None:
            raise NotFoundError("Không tìm thấy cấu hình phí")
        return fee

    async def update(self, fee_id: int, changes: Mapping[str, Any]) -> FeeConfig:
        unknown = set(changes) - _EDITABLE
        if unknown:
            raise BusinessRuleError(f"Không được sửa trường: {', '.join(sorted(unknown))}")
        fee = await self.get(fee_id)
        for key, val in changes.items():
            setattr(fee, key, val)
        self._validate(fee)
        updated = await self._fees.update(fee)
        await self._uow.commit()
        return updated

    async def deactivate(self, fee_id: int) -> None:
        """Xóa mềm: giữ lại dòng để đối soát đơn cũ."""
        fee = await self.get(fee_id)
        fee.is_active = False
        await self._fees.update(fee)
        await self._uow.commit()

    async def list_fees(self, *, fee_type: str | None, active_only: bool) -> list[FeeConfig]:
        return await self._fees.list_fees(fee_type=fee_type, active_only=active_only)

    async def list_current(self, *, on_date: date | None, fee_type: str | None) -> list[FeeConfig]:
        return await self._fees.list_current(on_date=on_date or today_vn(), fee_type=fee_type)

    @staticmethod
    def _validate(fee: FeeConfig) -> None:
        if fee.value is None or fee.value < Decimal(0):
            raise BusinessRuleError("Giá trị phí không được âm")
        if fee.unit == "PERCENT" and fee.value > Decimal(100):
            raise BusinessRuleError("Phí theo % không được vượt quá 100")
        if fee.tier_min is not None and fee.tier_min < 0:
            raise BusinessRuleError("tier_min không được âm")
        if fee.tier_min is not None and fee.tier_max is not None and fee.tier_max <= fee.tier_min:
            raise BusinessRuleError("tier_max phải lớn hơn tier_min")
