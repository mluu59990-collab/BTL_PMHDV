"""Kết nối CSDL bất đồng bộ (SQLAlchemy 2.0 async + asyncpg)."""
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,  # tự bỏ connection chết
)

# expire_on_commit=False: sau commit vẫn đọc được thuộc tính object (bắt buộc với async)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """1 request = 1 session. Không commit thì đóng session sẽ tự rollback."""
    async with SessionLocal() as session:
        yield session


async def check_database() -> None:
    """Ném lỗi nếu không kết nối được DB (dùng lúc khởi động + /health)."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
