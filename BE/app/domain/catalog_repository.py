from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from app.domain.catalog import CatalogRecord

T = TypeVar("T", bound=CatalogRecord)


class CatalogRepository(ABC, Generic[T]):
    @abstractmethod
    async def get(self, record_id: int, *, for_update: bool = False) -> T | None: ...

    @abstractmethod
    async def add(self, record: T) -> T: ...

    @abstractmethod
    async def update(self, record_id: int, changes: dict[str, Any]) -> T: ...

    @abstractmethod
    async def list(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        active_only: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[T], int]: ...
