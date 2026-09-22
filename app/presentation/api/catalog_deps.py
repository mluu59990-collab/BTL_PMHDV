from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.catalog_service import (
    BrandRightService,
    ProductService,
    ReferenceService,
)
from app.domain.catalog import ReferenceKind
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.repositories.catalog_repository import (
    brand_right_repository,
    product_repository,
    reference_repository,
)


def get_reference_service(
    kind: ReferenceKind, session: Annotated[AsyncSession, Depends(get_session)]
) -> ReferenceService:
    return ReferenceService(
        reference_repository(session, kind), SqlAlchemyUnitOfWork(session), kind
    )


def get_product_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProductService:
    return ProductService(
        product_repository(session),
        SqlAlchemyUnitOfWork(session),
        {kind: reference_repository(session, kind) for kind in ReferenceKind},
    )


def get_brand_right_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BrandRightService:
    return BrandRightService(
        brand_right_repository(session),
        SqlAlchemyUnitOfWork(session),
        product_repository(session),
        reference_repository(session, ReferenceKind.CATEGORIES),
    )
