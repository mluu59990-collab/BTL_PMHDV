"""Các 'cổng' mà tầng application cần từ bên ngoài (hash mật khẩu, JWT, transaction)."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import TokenType


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    type: TokenType
    jti: str
    expires_at: datetime
    role: str | None = None


class PasswordHasher(ABC):
    @abstractmethod
    async def hash(self, password: str) -> str: ...

    @abstractmethod
    async def verify(self, password: str, password_hash: str) -> bool: ...


class TokenProvider(ABC):
    @abstractmethod
    def create_access_token(self, *, user_id: int, role: str) -> IssuedToken: ...

    @abstractmethod
    def create_refresh_token(self, *, user_id: int) -> IssuedToken: ...

    @abstractmethod
    def decode(self, token: str, *, expected_type: TokenType) -> TokenPayload:
        """Ném AuthenticationError nếu token sai/hết hạn/sai loại."""


class UnitOfWork(ABC):
    """Ranh giới transaction: service gọi commit() khi xong một nghiệp vụ."""

    @abstractmethod
    async def commit(self) -> None:
        """Ném ConflictError nếu vi phạm ràng buộc (trùng dữ liệu...)."""

    @abstractmethod
    async def rollback(self) -> None: ...
