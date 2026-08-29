import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi import status as http_status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.bills import BillCreateRequest, BillResponse
from app.schemas.orders import OrderCreateRequest, OrderPreviewResponse, OrderResponse, OrderUpdateRequest
from app.services.kot_and_bill_service import send_kot_and_finalize_bill
from app.services.kot_service import build_kot_ticket_broadcast
from app.services.order_service import (
    apply_order_update,
    build_order_response,
    create_order,
    get_order_or_404,
    list_orders,
    preview_order_update,
)
from app.ws.manager import manager as ws_manager

_DUPLICATE_PARTY_DETAIL = (
    "That party label is already in use for an open order at this table — someone else "
    "just claimed it. Refresh and pick another."
)

# waiter/pos_user/pos_operator/tenant_admin can all build a cart; `kitchen` has no POS
# access whatsoever (CLAUDE.md §5) — enforced once here for the whole router.
router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    dependencies=[
        Depends(require_tenant_scope),
        Depends(require_role("tenant_admin", "pos_user", "waiter", "pos_operator")),
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


@router.post(
    "/{order_id}/kot-and-bill",
    response_model=BillResponse,
    status_code=201,
    dependencies=[Depends(require_role("tenant_admin", "pos_user", "pos_operator"))],
)
async def send_order_to_kot_and_bill(
    order_id: uuid.UUID,
    payload: BillCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillResponse:
    """Guided POS's non-seating "KOT + Print Bill" action (a `waiter` token is rejected
    with 403 here exactly as it is from `POST /bills`, same billing-role gate — this
    route both fires a KOT *and* bills). `order_id` in the path is authoritative; the
    body still carries the usual `BillCreateRequest` shape (coupon/payments/skip_print)
    so the frontend can reuse the same payload it already builds for `POST /bills`.
    """
    tenant = (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()
    req = payload.model_copy(update={"order_id": order_id})
    result, kot_result = await send_kot_and_finalize_bill(db, tenant, current_user, req)
    await db.commit()

    await ws_manager.broadcast(kot_result.location_id, build_kot_ticket_broadcast(kot_result))
    for stock_message in kot_result.stock_messages:
        await ws_manager.broadcast(kot_result.location_id, stock_message)
    await ws_manager.broadcast(result.location_id, {"type": "top_sellers_changed"})

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
