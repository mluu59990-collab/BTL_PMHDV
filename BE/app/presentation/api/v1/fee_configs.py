from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status

from app.application.services.fee_config_service import FeeConfigService
from app.domain.entities import FeeConfig
from app.domain.entities import User
from app.domain.enums import RoleCode
from app.presentation.api.deps import get_current_user, get_fee_config_service, require_roles
from app.presentation.schemas.fee_config import FeeConfigCreate, FeeConfigRead, FeeConfigUpdate

router = APIRouter(prefix="/fee-configs", tags=["Thang bảng phí"])

# Các trường không cho phép set null khi PATCH
_NOT_NULLABLE = ("value", "unit", "effective_date", "is_active")


@router.get("", response_model=list[FeeConfigRead], summary="Danh sách cấu hình phí (kể cả lịch sử)")
async def list_fee_configs(
    fee_type: str | None = Query(None, description="Vd: PURCHASE_SERVICE_FEE"),
    active_only: bool = True,
    _: User = Depends(get_current_user),
    service: FeeConfigService = Depends(get_fee_config_service),
):
    return await service.list_fees(fee_type=fee_type, active_only=active_only)


@router.get("/current", response_model=list[FeeConfigRead], summary="Biểu phí đang áp dụng")
async def list_current_fee_configs(
    fee_type: str | None = None,
    on_date: date | None = Query(None, description="Mặc định là hôm nay (giờ VN)"),
    _: User = Depends(get_current_user),
    service: FeeConfigService = Depends(get_fee_config_service),
):
    """Với mỗi bậc thang lấy dòng có `effective_date` mới nhất <= ngày cần tra."""
    return await service.list_current(on_date=on_date, fee_type=fee_type)


@router.get("/{fee_id}", response_model=FeeConfigRead, summary="Chi tiết 1 cấu hình phí")
async def get_fee_config(
    fee_id: int,
    _: User = Depends(get_current_user),
    service: FeeConfigService = Depends(get_fee_config_service),
):
    return await service.get(fee_id)


@router.post("", response_model=FeeConfigRead, status_code=status.HTTP_201_CREATED, summary="[Admin] Thêm cấu hình phí")
async def create_fee_config(
    body: FeeConfigCreate,
    admin: User = Depends(require_roles(RoleCode.ADMIN)),
    service: FeeConfigService = Depends(get_fee_config_service),
):
    return await service.create(FeeConfig(**body.model_dump()), actor_id=admin.id)


@router.patch("/{fee_id}", response_model=FeeConfigRead, summary="[Admin] Sửa cấu hình phí")
async def update_fee_config(
    fee_id: int,
    body: FeeConfigUpdate,
    _: User = Depends(require_roles(RoleCode.ADMIN)),
    service: FeeConfigService = Depends(get_fee_config_service),
):
    changes = body.model_dump(exclude_unset=True)
    for key in _NOT_NULLABLE:
        if key in changes and changes[key] is None:
            del changes[key]
    return await service.update(fee_id, changes)


@router.delete("/{fee_id}", status_code=status.HTTP_204_NO_CONTENT, summary="[Admin] Ngừng áp dụng (xóa mềm)")
async def deactivate_fee_config(
    fee_id: int,
    _: User = Depends(require_roles(RoleCode.ADMIN)),
    service: FeeConfigService = Depends(get_fee_config_service),
) -> Response:
    await service.deactivate(fee_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
