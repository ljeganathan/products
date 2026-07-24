import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tax_profile import TaxProfile


class TaxProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(
        self, profile_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> TaxProfile | None:
        return await self.db.scalar(
            select(TaxProfile).where(
                TaxProfile.id == profile_id, TaxProfile.tenant_id == tenant_id
            )
        )

    async def list_for_tenant(self, tenant_id: uuid.UUID) -> list[TaxProfile]:
        result = await self.db.execute(
            select(TaxProfile).where(TaxProfile.tenant_id == tenant_id).order_by(TaxProfile.name)
        )
        return list(result.scalars().all())

    async def unset_default_for_tenant(self, tenant_id: uuid.UUID) -> None:
        await self.db.execute(
            update(TaxProfile)
            .where(TaxProfile.tenant_id == tenant_id, TaxProfile.is_default.is_(True))
            .values(is_default=False)
        )

    async def create(self, profile: TaxProfile) -> TaxProfile:
        self.db.add(profile)
        await self.db.flush()
        return profile
