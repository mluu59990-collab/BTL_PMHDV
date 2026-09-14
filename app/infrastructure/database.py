import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Metadata chung cho các ORM model bổ sung từ buổi 2."""


class Database:
    def __init__(self, url: str, timeout_seconds: float = 5) -> None:
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.timeout_seconds = timeout_seconds

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        # Mỗi request sở hữu session riêng. Use case chủ động commit/transaction.
        async with self.session_factory() as session:
            try:
                yield session
            except BaseException:
                await session.rollback()
                raise

    async def ping(self) -> None:
        async with asyncio.timeout(self.timeout_seconds):
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self.engine.dispose()
