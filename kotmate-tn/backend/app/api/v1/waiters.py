import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.waiters import WaiterCreateRequest, WaiterResponse, WaiterUpdateRequest
from app.services.waiter_service import (
    create_waiter,
    get_waiter_by_user_id,
    get_waiter_or_404,
    list_waiters,
    update_waiter,
)

# Read access is broad (Phase 07 POS needs it for waiter assignment); writes are
# tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/waiters", tags=["waiters"], dependencies=[Depends(require_tenant_scope)])


@router.get("", response_model=list[WaiterResponse])
async def list_tenant_waiters(
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WaiterResponse]:
    waiters = await list_waiters(db, current_user.tenant_id, location_id)
    return [WaiterResponse.model_validate(w) for w in waiters]


@router.get("/me", response_model=WaiterResponse | None)
async def get_my_waiter_profile(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterResponse | None:
    """Resolves the logged-in `waiter`-role user's own Waiter Master row, if linked — the
    POS screen (Phase 07) uses this to auto-lock the waiter selector to themself.
    Returns null (not 404) when unlinked, since "no profile yet" is an expected state,
    not an error.
    """
    waiter = await get_waiter_by_user_id(db, current_user.tenant_id, current_user.id)
    return WaiterResponse.model_validate(waiter) if waiter else None


@router.post(
    "", response_model=WaiterResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_waiter(
    payload: WaiterCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterResponse:
    try:
        waiter = await create_waiter(db, current_user.tenant_id, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That waiter number is already in use at this location"
        ) from exc
    return WaiterResponse.model_validate(waiter)


@router.patch(
    "/{waiter_id}", response_model=WaiterResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_waiter(
    waiter_id: uuid.UUID,
    payload: WaiterUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterResponse:
    waiter = await get_waiter_or_404(db, current_user.tenant_id, waiter_id)
    try:
        waiter = await update_waiter(db, current_user.tenant_id, waiter, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That waiter number is already in use at this location"
        ) from exc
    return WaiterResponse.model_validate(waiter)
