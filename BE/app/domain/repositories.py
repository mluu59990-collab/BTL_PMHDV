"""Interface (hợp đồng) của repository. Implement nằm ở tầng infrastructure."""
from abc import ABC, abstractmethod
from datetime import date

from app.domain.entities import ExchangeRate, FeeConfig, RefreshToken, User
from app.domain.enums import RoleCode, UserStatus


class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    async def get_by_username(self, username: str) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def add(self, user: User) -> User: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...

    @abstractmethod
    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: RoleCode | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        """Trả về (danh sách, tổng số bản ghi khớp bộ lọc)."""


class RefreshTokenRepository(ABC):
    @abstractmethod
    async def add(self, token: RefreshToken) -> RefreshToken: ...

    @abstractmethod
    async def get_by_jti(self, jti: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, jti: str) -> bool:
        """Thu hồi token. Trả về False nếu token không tồn tại hoặc đã bị thu hồi trước đó."""

    @abstractmethod
    async def revoke_all_for_user(self, user_id: int) -> None: ...


class ExchangeRateRepository(ABC):
    @abstractmethod
    async def add(self, rate: ExchangeRate) -> ExchangeRate: ...

    @abstractmethod
    async def get_latest(self, currency_code: str) -> ExchangeRate | None: ...

    @abstractmethod
    async def list_latest_all(self) -> list[ExchangeRate]:
        """Tỷ giá mới nhất của mỗi loại tiền tệ."""

    @abstractmethod
    async def list_history(
        self, *, currency_code: str | None, offset: int, limit: int
    ) -> tuple[list[ExchangeRate], int]: ...


class FeeConfigRepository(ABC):
    @abstractmethod
    async def add(self, fee: FeeConfig) -> FeeConfig: ...

    @abstractmethod
    async def get_by_id(self, fee_id: int) -> FeeConfig | None: ...

    @abstractmethod
    async def update(self, fee: FeeConfig) -> FeeConfig: ...

    @abstractmethod
    async def list_fees(
        self, *, fee_type: str | None, active_only: bool
    ) -> list[FeeConfig]: ...

    @abstractmethod
    async def list_current(self, *, on_date: date, fee_type: str | None) -> list[FeeConfig]:
        """Với mỗi (fee_type, unit, tier_min): dòng active có effective_date mới nhất <= on_date."""
