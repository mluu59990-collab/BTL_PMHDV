from dataclasses import dataclass

from app.application.ports import PasswordHasher, TokenProvider, UnitOfWork
from app.core.clock import utcnow
from app.domain.entities import RefreshToken, User
from app.domain.enums import TokenType
from app.domain.exceptions import AuthenticationError
from app.domain.repositories import RefreshTokenRepository, UserRepository


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int  # số giây access token còn hiệu lực


class AuthService:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        tokens: TokenProvider,
    ):
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens

    async def login(self, username: str, password: str) -> TokenPair:
        user = await self._users.get_by_username(username.strip().lower())
        # Báo chung một câu để không lộ tài khoản nào tồn tại
        if user is None or not await self._hasher.verify(password, user.password_hash):
            raise AuthenticationError("Sai tên đăng nhập hoặc mật khẩu")
        if not user.is_active:
            raise AuthenticationError("Tài khoản đã bị khóa hoặc ngừng hoạt động")

        user.last_login_at = utcnow()
        await self._users.update(user)
        pair = await self._issue_pair(user)
        await self._uow.commit()
        return pair

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Xoay vòng refresh token: token cũ bị thu hồi, cấp cặp token mới."""
        payload = self._tokens.decode(refresh_token, expected_type=TokenType.REFRESH)

        user = await self._users.get_by_id(payload.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Tài khoản không tồn tại hoặc đã bị khóa")

        # Thu hồi nguyên tử: nếu False nghĩa là token không có trong DB / đã dùng rồi
        if not await self._refresh_tokens.revoke(payload.jti):
            raise AuthenticationError("Refresh token không hợp lệ hoặc đã bị thu hồi")

        pair = await self._issue_pair(user)
        await self._uow.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = self._tokens.decode(refresh_token, expected_type=TokenType.REFRESH)
        except AuthenticationError:
            return  # token hỏng/hết hạn thì coi như đã đăng xuất
        await self._refresh_tokens.revoke(payload.jti)
        await self._uow.commit()

    async def authenticate(self, access_token: str) -> User:
        """Dùng cho mọi endpoint cần đăng nhập. Luôn đọc user từ DB nên đổi quyền/khóa tài khoản có hiệu lực ngay."""
        payload = self._tokens.decode(access_token, expected_type=TokenType.ACCESS)
        user = await self._users.get_by_id(payload.user_id)
        if user is None or not user.is_active:
            raise AuthenticationError("Tài khoản không tồn tại hoặc đã bị khóa")
        return user

    async def _issue_pair(self, user: User) -> TokenPair:
        access = self._tokens.create_access_token(user_id=user.id, role=user.role.value)
        refresh = self._tokens.create_refresh_token(user_id=user.id)
        await self._refresh_tokens.add(
            RefreshToken(user_id=user.id, jti=refresh.jti, expires_at=refresh.expires_at)
        )
        expires_in = max(int((access.expires_at - utcnow()).total_seconds()), 0)
        return TokenPair(access_token=access.token, refresh_token=refresh.token, expires_in=expires_in)
