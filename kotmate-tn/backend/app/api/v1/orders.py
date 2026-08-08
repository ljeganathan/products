import uuid

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.orders import OrderCreateRequest, OrderPreviewResponse, OrderResponse, OrderUpdateRequest
from app.services.order_service import (
    apply_order_update,
    build_order_response,
    create_order,
    get_order_or_404,
    list_orders,
    preview_order_update,
)

_DUPLICATE_PARTY_DETAIL = (
    "That party label is already in use for an open order at this table — someone else "
    "just claimed it. Refresh and pick another."
)

# waiter/pos_user/tenant_admin can all build a cart; `kitchen` has no POS access
# whatsoever (CLAUDE.md §5) — enforced once here for the whole router.
router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[
        Depends(require_tenant_scope),
        Depends(require_role("tenant_admin", "pos_user", "waiter")),
    ],
)


@router.post("", response_model=OrderResponse, status_code=201)
async def create_tenant_order(
    payload: OrderCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    try:
        result = await create_order(db, current_user.tenant_id, current_user, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(http_status.HTTP_409_CONFLICT, _DUPLICATE_PARTY_DETAIL) from exc
    return result


@router.get("", response_model=list[OrderResponse])
async def list_tenant_orders(
    status: str | None = None,
    location_id: uuid.UUID | None = None,
    table_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OrderResponse]:
    orders = await list_orders(db, current_user.tenant_id, status, location_id, table_id)
    return [await build_order_response(db, order) for order in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_tenant_order(
    order_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    order = await get_order_or_404(db, current_user.tenant_id, order_id)
    return await build_order_response(db, order)


@router.patch("/{order_id}", response_model=OrderResponse | OrderPreviewResponse)
async def update_tenant_order(
    order_id: uuid.UUID,
    payload: OrderUpdateRequest,
    dry_run: bool = False,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse | OrderPreviewResponse:
    order = await get_order_or_404(db, current_user.tenant_id, order_id)

    if dry_run:
        return await preview_order_update(db, current_user.tenant_id, order, payload)

    try:
        result = await apply_order_update(db, current_user.tenant_id, current_user, order, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(http_status.HTTP_409_CONFLICT, _DUPLICATE_PARTY_DETAIL) from exc
    return result
