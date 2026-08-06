from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import PlatformSettings
from app.schemas.platform import MaintenanceSettingsResponse, MaintenanceSettingsUpdate

router = APIRouter(prefix="/maintenance", tags=["platform-maintenance"])


async def _get_settings_row(db: AsyncSession) -> PlatformSettings:
    # Singleton (id=1), always present — seeded by its own migration.
    return (await db.execute(select(PlatformSettings).where(PlatformSettings.id == 1))).scalar_one()


@router.get("", response_model=MaintenanceSettingsResponse)
async def get_maintenance_settings(db: AsyncSession = Depends(get_db)) -> PlatformSettings:
    return await _get_settings_row(db)


@router.patch("", response_model=MaintenanceSettingsResponse)
async def update_maintenance_settings(
    payload: MaintenanceSettingsUpdate, db: AsyncSession = Depends(get_db)
) -> PlatformSettings:
    settings_row = await _get_settings_row(db)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)
    await db.commit()
    return settings_row
