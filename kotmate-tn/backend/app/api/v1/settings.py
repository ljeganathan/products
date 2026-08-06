import uuid

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.hotel_master import HotelMasterResponse, HotelMasterUpdateRequest
from app.services.hotel_master_service import get_hotel_master, upload_hotel_master_logo, upsert_hotel_master

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
