import uuid

from fastapi import APIRouter, Depends, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.schemas.company_settings import (
    CompanySettingsOut,
    CompanySettingsUpdate,
    LogoUploadResponse,
)
from app.services.audit_service import record_audit_log
from app.services.company_settings_service import get_or_create_company_settings
from app.services.media_service import save_company_logo
from app.utils.store_scope import resolve_store_id

router = APIRouter(prefix="/settings/company", tags=["company-settings"])

require_admin = require_role(UserRole.ADMIN)


@router.get("", response_model=CompanySettingsOut)
async def get_company_settings(
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompanySettingsOut:
    assert current_user.tenant_id is not None
    target_store_id = resolve_store_id(current_user, store_id)
    settings = await get_or_create_company_settings(
        db, tenant_id=current_user.tenant_id, store_id=target_store_id
    )
    await db.commit()
    return CompanySettingsOut.model_validate(settings)


@router.patch("", response_model=CompanySettingsOut)
async def update_company_settings(
    payload: CompanySettingsUpdate,
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CompanySettingsOut:
    assert current_user.tenant_id is not None
    target_store_id = resolve_store_id(current_user, store_id)
    settings = await get_or_create_company_settings(
        db, tenant_id=current_user.tenant_id, store_id=target_store_id
    )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="company_settings.update",
        entity="company_settings",
        entity_id=settings.id,
    )
    await db.commit()
    return CompanySettingsOut.model_validate(settings)


@router.post("/logo", response_model=LogoUploadResponse)
async def upload_company_logo(
    file: UploadFile,
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LogoUploadResponse:
    assert current_user.tenant_id is not None
    target_store_id = resolve_store_id(current_user, store_id)
    settings = await get_or_create_company_settings(
        db, tenant_id=current_user.tenant_id, store_id=target_store_id
    )

    logo_url = await save_company_logo(
        file, tenant_id=current_user.tenant_id, store_id=target_store_id
    )
    settings.logo_url = logo_url

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="company_settings.logo_upload",
        entity="company_settings",
        entity_id=settings.id,
    )
    await db.commit()
    return LogoUploadResponse(logo_url=logo_url)
