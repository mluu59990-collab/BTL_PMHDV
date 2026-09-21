from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.domain.entities import RefreshToken
from app.domain.repositories import RefreshTokenRepository
from app.infrastructure.db.models import RefreshTokenModel
from app.infrastructure.db.unit_of_work import flush_or_conflict


def _to_entity(m: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=m.id,
        user_id=m.user_id,
        jti=m.jti,
        expires_at=m.expires_at,
        revoked_at=m.revoked_at,
        created_at=m.created_at,
    )


class SqlRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def add(self, token: RefreshToken) -> RefreshToken:
        m = RefreshTokenModel(user_id=token.user_id, jti=token.jti, expires_at=token.expires_at)
        self._s.add(m)
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        m = (await self._s.execute(select(RefreshTokenModel).where(RefreshTokenModel.jti == jti))).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def revoke(self, jti: str) -> bool:
        # UPDATE ... WHERE revoked_at IS NULL: 2 request cùng lúc chỉ 1 cái thắng
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.jti == jti, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=utcnow())
            .returning(RefreshTokenModel.id)
            .execution_options(synchronize_session=False)
        )
        return (await self._s.execute(stmt)).first() is not None

    async def revoke_all_for_user(self, user_id: int) -> None:
        stmt = (
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        await self._s.execute(stmt)
