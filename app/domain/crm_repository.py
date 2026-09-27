from abc import abstractmethod

from app.domain.catalog_repository import CatalogRepository


class CrmRepository(CatalogRepository):
    @abstractmethod
    async def membership_overlaps(
        self, customer_id, start, end, exclude_id=None
    ) -> bool: ...
