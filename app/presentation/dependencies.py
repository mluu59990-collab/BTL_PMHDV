from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Database


def get_database(request: Request) -> Database:
    return request.app.state.database


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with get_database(request).session() as session:
        yield session
