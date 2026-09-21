from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.application.services.auth_service import AuthService, TokenPair
from app.application.services.user_service import UserService
from app.domain.enums import RoleCode
from app.presentation.api.deps import get_auth_service, get_user_service
from app.presentation.schemas.auth import RefreshRequest, TokenResponse
from app.presentation.schemas.user import RegisterRequest, UserRead

router = APIRouter(prefix="/auth", tags=["Xác thực"])


def _token_response(pair: TokenPair) -> TokenResponse:
    return TokenResponse(access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in)


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, summary="Đăng ký tài khoản Khách hàng")
async def register(body: RegisterRequest, users: UserService = Depends(get_user_service)):
    """Đăng ký công khai luôn tạo vai trò CUSTOMER. Tài khoản nhân viên do Admin tạo qua `POST /users`."""
    return await users.create_user(
        username=body.username,
        password=body.password,
        full_name=body.full_name,
        email=body.email,
        phone=body.phone,
        role=RoleCode.CUSTOMER,
    )


@router.post("/login", response_model=TokenResponse, summary="Đăng nhập")
async def login(form: OAuth2PasswordRequestForm = Depends(), auth: AuthService = Depends(get_auth_service)):
    """Form-data `username` + `password` (chuẩn OAuth2 để nút Authorize trong Swagger dùng được)."""
    return _token_response(await auth.login(form.username, form.password))


@router.post("/refresh", response_model=TokenResponse, summary="Đổi refresh token lấy cặp token mới")
async def refresh(body: RefreshRequest, auth: AuthService = Depends(get_auth_service)):
    return _token_response(await auth.refresh(body.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Đăng xuất (thu hồi refresh token)")
async def logout(body: RefreshRequest, auth: AuthService = Depends(get_auth_service)) -> Response:
    await auth.logout(body.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
