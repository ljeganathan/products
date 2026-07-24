from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser, get_current_user
from app.models.enums import UserRole
from app.repositories.platform_settings_repository import PlatformSettingsRepository
from app.schemas.platform_settings import (
    MaintenanceStatusOut,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
)

router = APIRouter(prefix="/platform", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)


@router.get("/settings", response_model=PlatformSettingsOut)
async def get_platform_settings(
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PlatformSettingsOut:
    settings = await PlatformSettingsRepository(db).get_or_create()
    await db.commit()
    return PlatformSettingsOut.model_validate(settings)


@router.patch("/settings", response_model=PlatformSettingsOut)
async def update_platform_settings(
    payload: PlatformSettingsUpdate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PlatformSettingsOut:
    settings = await PlatformSettingsRepository(db).get_or_create()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    await db.flush()
    await db.commit()
    return PlatformSettingsOut.model_validate(settings)


@router.get("/maintenance-status", response_model=MaintenanceStatusOut)
async def get_maintenance_status(
    # Any authenticated role — the app shell checks this for every signed-in
    # user (Phase 7 task 1) and hides the resulting banner for product_owner
    # client-side, since a maintenance window never applies to the console.
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
    db: AsyncSession = Depends(get_db),
) -> MaintenanceStatusOut:
    settings = await PlatformSettingsRepository(db).get_or_create()
    await db.commit()
    return MaintenanceStatusOut.model_validate(settings)
