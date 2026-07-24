import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import check_printer_profile_limit
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.models.printer_profile import PrinterProfile
from app.repositories.printer_profile_repository import PrinterProfileRepository
from app.schemas.printer_profile import (
    PrinterProfileCreate,
    PrinterProfileOut,
    PrinterProfileUpdate,
)
from app.services.audit_service import record_audit_log
from app.utils.store_scope import resolve_store_id

router = APIRouter(prefix="/settings/printer-profiles", tags=["printer-profiles"])

require_admin = require_role(UserRole.ADMIN)
# A cashier needs to read which printer profile to send a receipt to (the
# POS print dispatch picks WebUSB vs the Local Print Agent based on this) —
# only create/update/delete stay admin-only, matching the tax-profiles
# read-only relaxation for the same reason.
require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


@router.get("", response_model=list[PrinterProfileOut])
async def list_printer_profiles(
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[PrinterProfileOut]:
    assert current_user.tenant_id is not None
    effective_store_id = store_id or current_user.store_id
    repo = PrinterProfileRepository(db)
    profiles = await repo.list_for_tenant(current_user.tenant_id, store_id=effective_store_id)
    return [PrinterProfileOut.model_validate(p) for p in profiles]


@router.post("", response_model=PrinterProfileOut, status_code=status.HTTP_201_CREATED)
async def create_printer_profile(
    payload: PrinterProfileCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PrinterProfileOut:
    assert current_user.tenant_id is not None
    store_id = resolve_store_id(current_user, payload.store_id)
    await check_printer_profile_limit(db, current_user.tenant_id)

    repo = PrinterProfileRepository(db)
    if payload.is_default:
        await repo.unset_default_for_store(current_user.tenant_id, store_id)

    profile = PrinterProfile(
        tenant_id=current_user.tenant_id,
        store_id=store_id,
        name=payload.name,
        type=payload.type,
        connection=payload.connection,
        is_default=payload.is_default,
        paper_width_chars=payload.paper_width_chars,
    )
    await repo.create(profile)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="printer_profile.create",
        entity="printer_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return PrinterProfileOut.model_validate(profile)


@router.patch("/{profile_id}", response_model=PrinterProfileOut)
async def update_printer_profile(
    profile_id: uuid.UUID,
    payload: PrinterProfileUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PrinterProfileOut:
    assert current_user.tenant_id is not None
    repo = PrinterProfileRepository(db)
    profile = await repo.get_by_id_for_tenant(profile_id, current_user.tenant_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Printer profile not found"
        )

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        await repo.unset_default_for_store(current_user.tenant_id, profile.store_id)

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="printer_profile.update",
        entity="printer_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return PrinterProfileOut.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    assert current_user.tenant_id is not None
    repo = PrinterProfileRepository(db)
    profile = await repo.get_by_id_for_tenant(profile_id, current_user.tenant_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Printer profile not found"
        )

    await db.delete(profile)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="printer_profile.delete",
        entity="printer_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return None
