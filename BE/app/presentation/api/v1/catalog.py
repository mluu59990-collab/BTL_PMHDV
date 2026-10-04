from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from app.application.services.catalog_service import (
    BrandRightService,
    ProductService,
    ReferenceService,
)
from app.domain.catalog import BrandRight, Product, ReferenceItem
from app.domain.entities import User
from app.domain.enums import RoleCode
from app.presentation.api.catalog_deps import (
    get_brand_right_service,
    get_product_service,
    get_reference_service,
)
from app.presentation.api.deps import get_current_user, require_roles
from app.presentation.schemas.catalog import (
    BrandRightCreate,
    BrandRightRead,
    BrandRightUpdate,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    ReferenceCreate,
    ReferenceRead,
    ReferenceUpdate,
)
from app.presentation.schemas.common import Page

router = APIRouter(tags=["Danh mục sản phẩm — Buổi 2"])
RecordId = Annotated[int, Path(gt=0, le=9223372036854775807)]
FilterId = Annotated[int | None, Query(gt=0, le=9223372036854775807)]
Admin = Annotated[User, Depends(require_roles(RoleCode.ADMIN))]
ProductWriter = Annotated[User, Depends(require_roles(RoleCode.PURCHASER))]
Reader = Annotated[User, Depends(get_current_user)]
RightsReader = Annotated[
    User, Depends(require_roles(RoleCode.SALE, RoleCode.PURCHASER))
]
References = Annotated[ReferenceService, Depends(get_reference_service)]
Products = Annotated[ProductService, Depends(get_product_service)]
Rights = Annotated[BrandRightService, Depends(get_brand_right_service)]


class Pagination:
    def __init__(
        self,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
        search: str | None = Query(None, max_length=150),
        active_only: bool = True,
    ):
        self.options = {
            "offset": offset,
            "limit": limit,
            "search": search,
            "active_only": active_only,
        }


Paging = Annotated[Pagination, Depends()]


async def page(service, schema, paging: Pagination, filters=None):
    items, total = await service.list(**paging.options, filters=filters)
    return Page[schema](
        items=[schema.model_validate(item) for item in items],
        total=total,
        offset=paging.options["offset"],
        limit=paging.options["limit"],
    )


# kind is a validated ReferenceKind path parameter in get_reference_service.
@router.get("/catalog/{kind}", response_model=Page[ReferenceRead])
async def list_references(service: References, paging: Paging, _: Reader):
    return await page(service, ReferenceRead, paging)


@router.get("/catalog/{kind}/{record_id}", response_model=ReferenceRead)
async def get_reference(record_id: RecordId, service: References, _: Reader):
    return await service.get(record_id)


@router.post("/catalog/{kind}", response_model=ReferenceRead, status_code=201)
async def create_reference(body: ReferenceCreate, service: References, _: Admin):
    return await service.create(ReferenceItem(**body.model_dump()))


@router.patch("/catalog/{kind}/{record_id}", response_model=ReferenceRead)
async def update_reference(
    record_id: RecordId, body: ReferenceUpdate, service: References, _: Admin
):
    return await service.update(record_id, body.model_dump(exclude_unset=True))


@router.delete("/catalog/{kind}/{record_id}", status_code=204)
async def delete_reference(record_id: RecordId, service: References, _: Admin):
    await service.deactivate(record_id)
    return Response(status_code=204)


@router.get("/products", response_model=Page[ProductRead])
async def list_products(
    service: Products,
    paging: Paging,
    _: Reader,
    category_id: FilterId = None,
    origin_country_id: FilterId = None,
    shipping_country_id: FilterId = None,
    unit_id: FilterId = None,
    package_type_id: FilterId = None,
):
    return await page(
        service,
        ProductRead,
        paging,
        {
            "category_id": category_id,
            "origin_country_id": origin_country_id,
            "shipping_country_id": shipping_country_id,
            "unit_id": unit_id,
            "package_type_id": package_type_id,
        },
    )


@router.get("/products/{record_id}", response_model=ProductRead)
async def get_product(record_id: RecordId, service: Products, _: Reader):
    return await service.get(record_id)


@router.post("/products", response_model=ProductRead, status_code=201)
async def create_product(body: ProductCreate, service: Products, _: ProductWriter):
    return await service.create(Product(**body.model_dump()))


@router.patch("/products/{record_id}", response_model=ProductRead)
async def update_product(
    record_id: RecordId, body: ProductUpdate, service: Products, _: ProductWriter
):
    return await service.update(record_id, body.model_dump(exclude_unset=True))


@router.delete("/products/{record_id}", status_code=204)
async def delete_product(record_id: RecordId, service: Products, _: ProductWriter):
    await service.deactivate(record_id)
    return Response(status_code=204)


@router.get("/brand-rights", response_model=Page[BrandRightRead])
async def list_rights(
    service: Rights,
    paging: Paging,
    _: RightsReader,
    product_id: FilterId = None,
    category_id: FilterId = None,
):
    return await page(
        service,
        BrandRightRead,
        paging,
        {"product_id": product_id, "category_id": category_id},
    )


@router.get("/brand-rights/{record_id}", response_model=BrandRightRead)
async def get_right(record_id: RecordId, service: Rights, _: RightsReader):
    return await service.get(record_id)


@router.post("/brand-rights", response_model=BrandRightRead, status_code=201)
async def create_right(body: BrandRightCreate, service: Rights, _: Admin):
    return await service.create(BrandRight(**body.model_dump()))


@router.patch("/brand-rights/{record_id}", response_model=BrandRightRead)
async def update_right(
    record_id: RecordId, body: BrandRightUpdate, service: Rights, _: Admin
):
    return await service.update(record_id, body.model_dump(exclude_unset=True))


@router.delete("/brand-rights/{record_id}", status_code=204)
async def delete_right(record_id: RecordId, service: Rights, _: Admin):
    await service.deactivate(record_id)
    return Response(status_code=204)
