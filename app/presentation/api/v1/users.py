from fastapi import APIRouter, Depends, Query, Response, status

from app.application.services.user_service import UserService
from app.domain.entities import User
from app.domain.enums import RoleCode, UserStatus
from app.presentation.api.deps import get_current_user, get_user_service, require_roles
from app.presentation.schemas.common import Page
from app.presentation.schemas.user import (
    AdminUserCreate,
    AdminUserUpdate,
    ChangePasswordRequest,
    UserRead,
    UserUpdateMe,
)

router = APIRouter(prefix="/users", tags=["Người dùng"])

# ---------- Thông tin cá nhân (mọi người dùng đã đăng nhập) - REQ-1.4 ----------


@router.get("/me", response_model=UserRead, summary="Thông tin của tôi")
async def get_me(current: User = Depends(get_current_user)):
    return current


@router.patch("/me", response_model=UserRead, summary="Sửa thông tin cá nhân")
async def update_me(
    body: UserUpdateMe,
    current: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
):
    return await users.update_profile(current.id, body.model_dump(exclude_unset=True))


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT, summary="Đổi mật khẩu")
async def change_password(
    body: ChangePasswordRequest,
    current: User = Depends(get_current_user),
    users: UserService = Depends(get_user_service),
) -> Response:
    await users.change_password(current.id, body.old_password, body.new_password)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Quản trị tài khoản (chỉ ADMIN) ----------


@router.get("", response_model=Page[UserRead], summary="[Admin] Danh sách người dùng")
async def list_users(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    role: RoleCode | None = None,
    status_: UserStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, description="Tìm theo username / họ tên / email"),
    _: User = Depends(require_roles(RoleCode.ADMIN)),
    users: UserService = Depends(get_user_service),
):
    items, total = await users.list_users(offset=offset, limit=limit, role=role, status=status_, search=search)
    return Page[UserRead](items=[UserRead.model_validate(u) for u in items], total=total, offset=offset, limit=limit)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="[Admin] Tạo tài khoản (chọn vai trò)")
async def create_user(
    body: AdminUserCreate,
    _: User = Depends(require_roles(RoleCode.ADMIN)),
    users: UserService = Depends(get_user_service),
):
    return await users.create_user(
        username=body.username,
        password=body.password,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        role=body.role,
    )


@router.patch("/{user_id}", response_model=UserRead, summary="[Admin] Sửa thông tin / đổi vai trò / khóa tài khoản")
async def admin_update_user(
    user_id: int,
    body: AdminUserUpdate,
    actor: User = Depends(require_roles(RoleCode.ADMIN)),
    users: UserService = Depends(get_user_service),
):
    return await users.admin_update_user(actor=actor, user_id=user_id, changes=body.model_dump(exclude_unset=True))
