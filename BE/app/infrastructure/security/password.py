import asyncio

from argon2 import PasswordHasher as Argon2
from argon2.exceptions import InvalidHashError, VerificationError

from app.application.ports import PasswordHasher


class Argon2PasswordHasher(PasswordHasher):
    """Argon2id (SRS B.4.2). Hash tốn CPU nên chạy trong thread để không chặn event loop."""

    def __init__(self) -> None:
        self._argon2 = Argon2()

    async def hash(self, password: str) -> str:
        return await asyncio.to_thread(self._argon2.hash, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        def _verify() -> bool:
            try:
                return self._argon2.verify(password_hash, password)
            except (VerificationError, InvalidHashError):
                return False

        return await asyncio.to_thread(_verify)
