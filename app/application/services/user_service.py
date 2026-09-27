from collections.abc import Mapping
from typing import Any

from app.application.ports import PasswordHasher, UnitOfWork
from app.domain.entities import User
from app.domain.enums import RoleCode, UserStatus
from app.domain.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.repositories import RefreshTokenRepository, UserRepository

_SELF_EDITABLE = {"full_name", "phone", "email"}
_ADMIN_EDITABLE = _SELF_EDITABLE | {"role", "status"}


class UserService:
    def __init__(
        self,
        users: UserRepository,
        refresh_tokens: RefreshTokenRepository,
        uow: UnitOfWork,
        hasher: PasswordHasher,
    ):
        self._users = users
        self._refresh_tokens = refresh_tokens
        self._uow = uow
        self._hasher = hasher

    # ---------- tạo tài khoản ----------
    async def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        role: RoleCode,
        email: str | None = None,
        phone: str | None = None,
    ) -> User:
        if not full_name.strip():
            raise BusinessRuleError("Họ tên không được để trống")
        username = username.strip().lower()
        await self._ensure_username_free(username)
        if email:
            await self._ensure_email_free(email)

        user = User(
            username=username,
            full_name=full_name.strip(),
            email=email.strip().lower() if email else None,
            phone=phone,
            password_hash=await self._hasher.hash(password),
            role=role,
        )
        created = await self._users.add(user)
        await self._uow.commit()
        return created

    # ---------- đọc ----------
    async def get(self, user_id: int) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Không tìm thấy người dùng")
        return user

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: RoleCode | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        return await self._users.list_users(offset=offset, limit=limit, role=role, status=status, search=search)

    # ---------- cập nhật ----------
    async def update_profile(self, user_id: int, changes: Mapping[str, Any]) -> User:
        """Người dùng tự sửa thông tin cá nhân (REQ-1.4)."""
        self._check_keys(changes, _SELF_EDITABLE)
        user = await self.get(user_id)
        await self._apply_common_changes(user, changes)
        updated = await self._users.update(user)
        await self._uow.commit()
        return updated

    async def admin_update_user(self, *, actor: User, user_id: int, changes: Mapping[str, Any]) -> User:
        self._check_keys(changes, _ADMIN_EDITABLE)
        user = await self.get(user_id)

        if actor.id == user.id and ("role" in changes or "status" in changes):
            raise BusinessRuleError("Không thể tự đổi vai trò/trạng thái của chính mình")

        await self._apply_common_changes(user, changes)
        if changes.get("role") is not None:
            user.role = changes["role"]  # quyền đọc lại từ DB ở mỗi request nên có hiệu lực ngay
        deactivated = False
        if changes.get("status") is not None:
            deactivated = changes["status"] != UserStatus.ACTIVE
            user.status = changes["status"]

        updated = await self._users.update(user)
        if deactivated:
            await self._refresh_tokens.revoke_all_for_user(user.id)  # khóa tài khoản -> đăng xuất mọi thiết bị
        await self._uow.commit()
        return updated

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        user = await self.get(user_id)
        if not await self._hasher.verify(old_password, user.password_hash):
            raise BusinessRuleError("Mật khẩu hiện tại không đúng")
        if old_password == new_password:
            raise BusinessRuleError("Mật khẩu mới phải khác mật khẩu hiện tại")
        user.password_hash = await self._hasher.hash(new_password)
        await self._users.update(user)
        await self._refresh_tokens.revoke_all_for_user(user.id)  # đăng xuất mọi thiết bị
        await self._uow.commit()

    # ---------- helper ----------
    @staticmethod
    def _check_keys(changes: Mapping[str, Any], allowed: set[str]) -> None:
        unknown = set(changes) - allowed
        if unknown:
            raise BusinessRuleError(f"Không được sửa trường: {', '.join(sorted(unknown))}")

    async def _apply_common_changes(self, user: User, changes: Mapping[str, Any]) -> None:
        if "full_name" in changes:
            if not changes["full_name"] or not changes["full_name"].strip():
                raise BusinessRuleError("Họ tên không được để trống")
            user.full_name = changes["full_name"].strip()
        if "phone" in changes:
            user.phone = changes["phone"]
        if "email" in changes:
            new_email = changes["email"].strip().lower() if changes["email"] else None
            if new_email and new_email != user.email:
                await self._ensure_email_free(new_email)
            user.email = new_email

    async def _ensure_username_free(self, username: str) -> None:
        if await self._users.get_by_username(username):
            raise ConflictError("Tên đăng nhập đã tồn tại")

    async def _ensure_email_free(self, email: str) -> None:
        if await self._users.get_by_email(email.strip().lower()):
            raise ConflictError("Email đã được sử dụng")
