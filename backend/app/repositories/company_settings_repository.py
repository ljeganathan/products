import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_settings import CompanySettings


class CompanySettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_store(
        self, tenant_id: uuid.UUID, store_id: uuid.UUID
    ) -> CompanySettings | None:
        return await self.db.scalar(
            select(CompanySettings).where(
                CompanySettings.tenant_id == tenant_id, CompanySettings.store_id == store_id
            )
        )

    async def create(self, settings: CompanySettings) -> CompanySettings:
        self.db.add(settings)
        await self.db.flush()
        return settings
