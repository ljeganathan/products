import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.hotel_master import HotelMasterResponse, HotelMasterUpdateRequest
from app.schemas.stock import StockManagementSettingsRequest, StockManagementSettingsResponse
from app.services.hotel_master_service import (
    get_hotel_master,
    remove_hotel_master_logo,
    upload_hotel_master_logo,
    upsert_hotel_master,
)
from app.services.stock_service import has_stock_management_feature
from app.services.tenant_onboarding import get_active_plan

# Hotel Master (Phase 10) — tenant_admin-only writes; reads broad since a future
# customer-facing bill-preview screen or another staff role could reasonably need to
# see the same info this form edits.
router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_tenant_scope)])


async def _get_tenant(db: AsyncSession, current_user: CurrentUser) -> Tenant:
    return (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()


@router.get("/hotel-master", response_model=HotelMasterResponse)
async def get_tenant_hotel_master(
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    return await get_hotel_master(db, current_user.tenant_id, location_id)


@router.put(
    "/hotel-master", response_model=HotelMasterResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def upsert_tenant_hotel_master(
    payload: HotelMasterUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    result = await upsert_hotel_master(db, current_user.tenant_id, payload)
    await db.commit()
    return result


@router.patch(
    "/stock-management",
    response_model=StockManagementSettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_stock_management_setting(
    payload: StockManagementSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StockManagementSettingsResponse:
    """The tenant-level kill switch (Pro/Pro Max only) — soft-disable, never touches
    items.track_inventory/available_qty, so re-enabling restores prior config exactly.
    """
    plan = await get_active_plan(db, current_user.tenant_id)
    if not has_stock_management_feature(plan.features if plan else None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Stock management isn't available on your current plan. Upgrade to Pro to use it.",
        )
    tenant = await _get_tenant(db, current_user)
    tenant.stock_management_enabled = payload.enabled
    await db.commit()
    return StockManagementSettingsResponse(enabled=tenant.stock_management_enabled)


@router.post(
    "/hotel-master/{location_id}/logo",
    response_model=HotelMasterResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def upload_tenant_hotel_master_logo(
    location_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    tenant = await _get_tenant(db, current_user)
    result = await upload_hotel_master_logo(db, tenant, location_id, file)
    await db.commit()
    return result


@router.delete(
    "/hotel-master/{location_id}/logo",
    response_model=HotelMasterResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def delete_tenant_hotel_master_logo(
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    result = await remove_hotel_master_logo(db, current_user.tenant_id, location_id)
    await db.commit()
    return result
