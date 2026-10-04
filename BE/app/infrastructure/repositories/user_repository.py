from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import utcnow
from app.domain.entities import User
from app.domain.enums import RoleCode, UserStatus
from app.domain.exceptions import BusinessRuleError
from app.domain.repositories import UserRepository
from app.infrastructure.db.models import RoleModel, UserModel
from app.infrastructure.db.unit_of_work import flush_or_conflict


def _to_entity(m: UserModel) -> User:
    return User(
        id=m.id,
        username=m.username,
        email=m.email,
        full_name=m.full_name,
        phone=m.phone,
        password_hash=m.password_hash,
        role=RoleCode(m.role.code),
        balance=m.balance,
        status=UserStatus(m.status),
        last_login_at=m.last_login_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._s = session

    async def _get_role(self, code: RoleCode) -> RoleModel:
        role = (await self._s.execute(select(RoleModel).where(RoleModel.code == code.value))).scalar_one_or_none()
        if role is None:
            raise BusinessRuleError(f"Vai trò {code.value} chưa có trong bảng roles (đã chạy 02_seed_data.sql chưa?)")
        return role

    async def get_by_id(self, user_id: int) -> User | None:
        m = await self._s.get(UserModel, user_id)
        return _to_entity(m) if m else None

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(UserModel).where(func.lower(UserModel.username) == username.lower())
        m = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(func.lower(UserModel.email) == email.lower())
        m = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def add(self, user: User) -> User:
        m = UserModel(
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            phone=user.phone,
            password_hash=user.password_hash,
            role=await self._get_role(user.role),
            balance=user.balance,
            status=user.status.value,
        )
        self._s.add(m)
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def update(self, user: User) -> User:
        m = await self._s.get(UserModel, user.id)
        m.email = user.email
        m.full_name = user.full_name
        m.phone = user.phone
        m.password_hash = user.password_hash
        m.balance = user.balance
        m.status = user.status.value
        m.last_login_at = user.last_login_at
        m.updated_at = utcnow()
        if m.role.code != user.role.value:
            m.role = await self._get_role(user.role)
        await flush_or_conflict(self._s)
        return _to_entity(m)

    async def list_users(
        self,
        *,
        offset: int,
        limit: int,
        role: RoleCode | None = None,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> tuple[list[User], int]:
        conds = []
        if role:
            conds.append(UserModel.role_id == select(RoleModel.id).where(RoleModel.code == role.value).scalar_subquery())
        if status:
            conds.append(UserModel.status == status.value)
        if search:
            conds.append(
                or_(
                    UserModel.username.icontains(search, autoescape=True),
                    UserModel.full_name.icontains(search, autoescape=True),
                    UserModel.email.icontains(search, autoescape=True),
                )
            )
        total = (await self._s.execute(select(func.count()).select_from(UserModel).where(*conds))).scalar_one()
        rows = (
            await self._s.execute(select(UserModel).where(*conds).order_by(UserModel.id).offset(offset).limit(limit))
        ).scalars().all()
        return [_to_entity(m) for m in rows], total
