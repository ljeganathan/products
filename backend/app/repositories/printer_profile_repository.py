import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.printer_profile import PrinterProfile


class PrinterProfileRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id_for_tenant(
        self, profile_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> PrinterProfile | None:
        return await self.db.scalar(
            select(PrinterProfile).where(
                PrinterProfile.id == profile_id, PrinterProfile.tenant_id == tenant_id
            )
        )

    async def list_for_tenant(
        self, tenant_id: uuid.UUID, *, store_id: uuid.UUID | None
    ) -> list[PrinterProfile]:
        stmt = select(PrinterProfile).where(PrinterProfile.tenant_id == tenant_id)
        if store_id is not None:
            stmt = stmt.where(PrinterProfile.store_id == store_id)
        result = await self.db.execute(stmt.order_by(PrinterProfile.name))
        return list(result.scalars().all())

    async def unset_default_for_store(self, tenant_id: uuid.UUID, store_id: uuid.UUID) -> None:
        await self.db.execute(
            update(PrinterProfile)
            .where(
                PrinterProfile.tenant_id == tenant_id,
                PrinterProfile.store_id == store_id,
                PrinterProfile.is_default.is_(True),
            )
            .values(is_default=False)
        )

    async def create(self, profile: PrinterProfile) -> PrinterProfile:
        self.db.add(profile)
        await self.db.flush()
        return profile
