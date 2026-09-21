from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports import UnitOfWork
from app.domain.exceptions import ConflictError

CONFLICT_MESSAGE = "Dữ liệu bị trùng hoặc vi phạm ràng buộc"


async def flush_or_conflict(session: AsyncSession) -> None:
    """flush() và đổi lỗi ràng buộc DB (unique, check...) thành ConflictError của domain."""
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError(CONFLICT_MESSAGE) from exc


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def commit(self) -> None:
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError(CONFLICT_MESSAGE) from exc

    async def rollback(self) -> None:
        await self._session.rollback()
