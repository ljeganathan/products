import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import TenantLocation
from app.schemas.locations import (
    LocationCreateRequest,
    LocationOption,
    LocationResponse,
    LocationUpdateRequest,
)
from app.services.location_service import (
    create_location,
    get_location_or_404,
    list_managed_locations,
    update_location,
)

# Read-only, broadly accessible to any tenant-scoped role (not just tenant_admin) —
# waiter/table master (Phase 06) and the POS location switcher (Phase 07) all need to
# list a tenant's locations, and location name is not sensitive data. Company Master
# CRUD (Phase 10) is tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/locations", tags=["locations"], dependencies=[Depends(require_tenant_scope)])


@router.get("", response_model=list[LocationOption])
async def list_tenant_locations(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocationOption]:
    rows = (
        await db.execute(
            select(TenantLocation)
            .where(TenantLocation.tenant_id == current_user.tenant_id, TenantLocation.is_active.is_(True))
            .order_by(TenantLocation.name)
        )
    ).scalars().all()
    return [LocationOption.model_validate(row) for row in rows]


@router.get(
    "/manage", response_model=list[LocationResponse], dependencies=[Depends(require_role("tenant_admin"))]
)
async def list_managed_tenant_locations(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[LocationResponse]:
    """Full detail, including deactivated locations — backs the Settings > Locations
    tab (Phase 10), distinct from the broad `GET /locations` picker above.
    """
    locations = await list_managed_locations(db, current_user.tenant_id)
    return [LocationResponse.model_validate(loc) for loc in locations]


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_location(
    payload: LocationCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    location = await create_location(db, current_user.tenant_id, payload)
    await db.commit()
    return LocationResponse.model_validate(location)


@router.patch(
    "/{location_id}", response_model=LocationResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_location(
    location_id: uuid.UUID,
    payload: LocationUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LocationResponse:
    location = await get_location_or_404(db, current_user.tenant_id, location_id)
    location = await update_location(db, current_user.tenant_id, location, payload)
    await db.commit()
    return LocationResponse.model_validate(location)
