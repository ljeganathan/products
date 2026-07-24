import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TenantStatus
from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        return await self.db.scalar(select(Tenant).where(Tenant.id == tenant_id))

    async def get_by_owner_email(self, owner_email: str) -> Tenant | None:
        return await self.db.scalar(select(Tenant).where(Tenant.owner_email == owner_email))

    async def list_all(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
        status: TenantStatus | None = None,
    ) -> tuple[list[Tenant], int]:
        query = select(Tenant)
        if search:
            like = f"%{search}%"
            query = query.where(
                or_(Tenant.name.ilike(like), Tenant.owner_email.ilike(like))
            )
        if status is not None:
            query = query.where(Tenant.status == status)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.execute(
            query.order_by(Tenant.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total or 0

    async def create(self, tenant: Tenant) -> Tenant:
        self.db.add(tenant)
        await self.db.flush()
        return tenant
