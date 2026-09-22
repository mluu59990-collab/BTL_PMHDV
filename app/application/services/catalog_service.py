from dataclasses import fields, replace
from typing import Any, Generic

from app.application.ports import UnitOfWork
from app.domain.catalog import BrandRight, Product, ReferenceItem, ReferenceKind
from app.domain.catalog_repository import CatalogRepository, T
from app.domain.exceptions import BusinessRuleError, NotFoundError


class CatalogService(Generic[T]):
    def __init__(self, repository: CatalogRepository[T], uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    async def get(self, record_id: int, *, for_update: bool = False) -> T:
        record = await self.repository.get(record_id, for_update=for_update)
        if record is None:
            raise NotFoundError("Không tìm thấy bản ghi danh mục")
        return record

    async def validate(self, record: T, changes: dict[str, Any] | None = None) -> None:
        pass

    async def create(self, record: T) -> T:
        await self.validate(record)
        result = await self.repository.add(record)
        await self.uow.commit()
        return result

    async def update(self, record_id: int, changes: dict[str, Any]) -> T:
        record = await self.get(record_id, for_update=True)
        allowed = {f.name for f in fields(record)} - {"id", "created_at", "updated_at"}
        if set(changes) - allowed:
            raise BusinessRuleError("Trường cập nhật không hợp lệ")
        await self.validate(replace(record, **changes), changes)
        result = await self.repository.update(record_id, changes)
        await self.uow.commit()
        return result

    async def deactivate(self, record_id: int) -> None:
        await self.get(record_id, for_update=True)
        await self.repository.update(record_id, {"is_active": False})
        await self.uow.commit()

    async def list(self, **kwargs) -> tuple[list[T], int]:
        return await self.repository.list(**kwargs)


class ReferenceService(CatalogService[ReferenceItem]):
    def __init__(self, repository, uow, kind: ReferenceKind):
        super().__init__(repository, uow)
        self.kind = kind

    async def validate(self, record: ReferenceItem, changes=None) -> None:
        if not record.name.strip() or not record.code.strip():
            raise BusinessRuleError("Mã và tên không được để trống")
        if self.kind == ReferenceKind.COUNTRIES and (
            len(record.code) != 2
            or not record.code.isascii()
            or not record.code.isalpha()
        ):
            raise BusinessRuleError("Mã nước phải gồm 2 chữ cái, ví dụ CN, VN")


class ProductService(CatalogService[Product]):
    def __init__(
        self,
        repository,
        uow,
        references: dict[ReferenceKind, CatalogRepository[ReferenceItem]],
    ):
        super().__init__(repository, uow)
        self.references = references

    async def validate(self, record: Product, changes=None) -> None:
        if (
            not record.name.strip()
            or not record.sku.strip()
            or record.reference_price < 0
        ):
            raise BusinessRuleError("Tên, mã hoặc giá sản phẩm không hợp lệ")
        links = {
            "origin_country_id": ReferenceKind.COUNTRIES,
            "shipping_country_id": ReferenceKind.COUNTRIES,
            "unit_id": ReferenceKind.UNITS,
            "package_type_id": ReferenceKind.PACKAGE_TYPES,
            "category_id": ReferenceKind.CATEGORIES,
        }
        for field, kind in links.items():
            # Existing links remain readable after a reference is deactivated.
            # Revalidate all links on creation/reactivation, otherwise changed links only.
            if (
                changes is not None
                and field not in changes
                and not changes.get("is_active")
            ):
                continue
            ref_id = getattr(record, field)
            if ref_id is not None:
                ref = await self.references[kind].get(ref_id)
                if ref is None or not ref.is_active:
                    raise BusinessRuleError(
                        f"{field}: danh mục không tồn tại hoặc đã ngừng sử dụng"
                    )


class BrandRightService(CatalogService[BrandRight]):
    def __init__(self, repository, uow, products, categories):
        super().__init__(repository, uow)
        self.products = products
        self.categories = categories

    async def validate(self, record: BrandRight, changes=None) -> None:
        if (record.product_id is None) == (record.category_id is None):
            raise BusinessRuleError(
                "Quyền thương hiệu phải gắn với đúng một sản phẩm hoặc ngành hàng"
            )
        if (
            record.valid_from
            and record.valid_until
            and record.valid_until < record.valid_from
        ):
            raise BusinessRuleError("Ngày kết thúc không được trước ngày bắt đầu")
        if not record.brand_name.strip() or not record.holder_name.strip():
            raise BusinessRuleError(
                "Tên thương hiệu và chủ thể quyền không được để trống"
            )
        if (
            changes is None
            or {"product_id", "category_id", "is_active"} & changes.keys()
        ):
            target = (
                await self.products.get(record.product_id)
                if record.product_id is not None
                else await self.categories.get(record.category_id)
            )
            if target is None or not target.is_active:
                raise BusinessRuleError(
                    "Sản phẩm/ngành hàng không tồn tại hoặc đã ngừng sử dụng"
                )
