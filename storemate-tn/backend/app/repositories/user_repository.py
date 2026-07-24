import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        return await self.db.scalar(select(User).where(User.email == email))

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.db.scalar(select(User).where(User.id == user_id))

    async def get_by_id_for_tenant(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> User | None:
        return await self.db.scalar(
            select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        )

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, page: int, page_size: int, search: str | None
    ) -> tuple[list[User], int]:
        stmt = select(User).where(User.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(User).where(User.tenant_id == tenant_id)

        if search:
            pattern = f"%{search}%"
            search_filter = User.name.ilike(pattern) | User.email.ilike(pattern)
            stmt = stmt.where(search_filter)
            count_stmt = count_stmt.where(search_filter)

        total = await self.db.scalar(count_stmt) or 0
        stmt = stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.flush()
        return user
