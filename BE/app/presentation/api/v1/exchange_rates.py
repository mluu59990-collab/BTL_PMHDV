from fastapi import APIRouter, Depends, Query, status

from app.application.services.exchange_rate_service import ExchangeRateService
from app.domain.entities import User
from app.domain.enums import CurrencyCode, RoleCode
from app.presentation.api.deps import get_current_user, get_exchange_rate_service, require_roles
from app.presentation.schemas.common import Page
from app.presentation.schemas.exchange_rate import ExchangeRateCreate, ExchangeRateRead

router = APIRouter(prefix="/exchange-rates", tags=["Tỷ giá"])


@router.get("/current", response_model=list[ExchangeRateRead], summary="Tỷ giá hiện hành của tất cả ngoại tệ")
async def get_current_rates(
    _: User = Depends(get_current_user),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
):
    """Dùng cho khung tỷ giá trên trang tổng quan: 1 NDT = ? VNĐ, 1 USD = ? VNĐ."""
    return await service.get_current_all()


@router.get("/current/{currency_code}", response_model=ExchangeRateRead, summary="Tỷ giá hiện hành của 1 ngoại tệ")
async def get_current_rate(
    currency_code: CurrencyCode,
    _: User = Depends(get_current_user),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
):
    return await service.get_current(currency_code)


@router.get("/history", response_model=Page[ExchangeRateRead], summary="Lịch sử thay đổi tỷ giá")
async def get_rate_history(
    currency_code: CurrencyCode | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
):
    items, total = await service.history(currency=currency_code, offset=offset, limit=limit)
    return Page[ExchangeRateRead](
        items=[ExchangeRateRead.model_validate(i) for i in items], total=total, offset=offset, limit=limit
    )


@router.post("", response_model=ExchangeRateRead, status_code=status.HTTP_201_CREATED, summary="[Admin] Cập nhật tỷ giá")
async def set_rate(
    body: ExchangeRateCreate,
    admin: User = Depends(require_roles(RoleCode.ADMIN)),
    service: ExchangeRateService = Depends(get_exchange_rate_service),
):
    """Mỗi lần cập nhật tạo 1 dòng mới, dòng cũ giữ làm lịch sử để đối soát đơn cũ."""
    return await service.set_rate(currency=body.currency_code, rate=body.rate, note=body.note, actor_id=admin.id)
