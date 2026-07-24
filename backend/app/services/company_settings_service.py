import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company_settings import CompanySettings
from app.models.store import Store
from app.repositories.company_settings_repository import CompanySettingsRepository


async def get_or_create_company_settings(
    db: AsyncSession, *, tenant_id: uuid.UUID, store_id: uuid.UUID
) -> CompanySettings:
    """Lazily provisions a company_settings row from the store record on
    first access, so neither the Settings screen nor a same-day first sale's
    receipt printing has to fail just because nobody visited Settings yet."""
    repo = CompanySettingsRepository(db)
    settings = await repo.get_by_store(tenant_id, store_id)
    if settings is not None:
        return settings

    store = await db.get(Store, store_id)
    if store is None or store.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    settings = CompanySettings(
        tenant_id=tenant_id,
        store_id=store_id,
        legal_name=store.name,
        display_name=store.name,
        address=store.address or "",
        gstin=store.gstin,
        phone=store.phone,
    )
    return await repo.create(settings)
