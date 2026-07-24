import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.models.tax_profile import TaxProfile
from app.repositories.tax_profile_repository import TaxProfileRepository
from app.schemas.tax_profile import TaxProfileCreate, TaxProfileOut, TaxProfileUpdate
from app.services.audit_service import record_audit_log
from app.services.tax_profile_service import check_tax_slab_warning

router = APIRouter(prefix="/settings/tax-profiles", tags=["tax-profiles"])

require_admin = require_role(UserRole.ADMIN)
# Rates are read-only reference data a cashier needs to bill correctly
# (the POS cart preview computes CGST/SGST client-side) — only
# create/update/delete stay admin-only, matching the Stock/Item/Category
# "view-only" pattern in CLAUDE.md §5.
require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)


def _to_out(profile: TaxProfile) -> TaxProfileOut:
    out = TaxProfileOut.model_validate(profile)
    out.warning = check_tax_slab_warning(profile.cgst_pct, profile.sgst_pct, profile.igst_pct)
    return out


@router.get("", response_model=list[TaxProfileOut])
async def list_tax_profiles(
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> list[TaxProfileOut]:
    assert current_user.tenant_id is not None
    repo = TaxProfileRepository(db)
    profiles = await repo.list_for_tenant(current_user.tenant_id)
    return [_to_out(p) for p in profiles]


@router.post("", response_model=TaxProfileOut, status_code=status.HTTP_201_CREATED)
async def create_tax_profile(
    payload: TaxProfileCreate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TaxProfileOut:
    assert current_user.tenant_id is not None
    repo = TaxProfileRepository(db)

    if payload.is_default:
        await repo.unset_default_for_tenant(current_user.tenant_id)

    profile = TaxProfile(
        tenant_id=current_user.tenant_id,
        name=payload.name,
        cgst_pct=payload.cgst_pct,
        sgst_pct=payload.sgst_pct,
        igst_pct=payload.igst_pct,
        is_default=payload.is_default,
    )
    await repo.create(profile)
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="tax_profile.create",
        entity="tax_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return _to_out(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tax_profile(
    profile_id: uuid.UUID,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    assert current_user.tenant_id is not None
    repo = TaxProfileRepository(db)
    profile = await repo.get_by_id_for_tenant(profile_id, current_user.tenant_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax profile not found")

    await db.delete(profile)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tax profile is still referenced by items",
        ) from exc

    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="tax_profile.delete",
        entity="tax_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return None


@router.patch("/{profile_id}", response_model=TaxProfileOut)
async def update_tax_profile(
    profile_id: uuid.UUID,
    payload: TaxProfileUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TaxProfileOut:
    assert current_user.tenant_id is not None
    repo = TaxProfileRepository(db)
    profile = await repo.get_by_id_for_tenant(profile_id, current_user.tenant_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tax profile not found")

    update_data = payload.model_dump(exclude_unset=True)
    if update_data.get("is_default") is True:
        await repo.unset_default_for_tenant(current_user.tenant_id)

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await record_audit_log(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.user_id,
        action="tax_profile.update",
        entity="tax_profile",
        entity_id=profile.id,
    )
    await db.commit()
    return _to_out(profile)
