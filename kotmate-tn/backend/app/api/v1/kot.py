import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Order, Tenant
from app.schemas.kot import ActiveKotTicketResponse, KotSendRequest, KotSendResponse, KotTicketStatusUpdate
from app.services.kot_service import (
    build_active_ticket_response,
    build_kot_ticket_broadcast,
    clear_billed_ticket,
    get_ticket_or_404,
    has_kds_feature,
    list_active_tickets,
    send_kot,
    update_ticket_status,
)
from app.services.tenant_onboarding import get_active_plan
from app.ws.manager import manager as ws_manager

router = APIRouter(prefix="/kot", tags=["kot"], dependencies=[Depends(require_tenant_scope)])

_KDS_UPGRADE_MESSAGE = "The KOT screen is only available on Pro Max. Upgrade to unlock it."


async def _get_tenant(db: AsyncSession, current_user: CurrentUser) -> Tenant:
    return (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()


async def _require_kds_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    plan = await get_active_plan(db, tenant_id)
    if not has_kds_feature(plan.features if plan else None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, _KDS_UPGRADE_MESSAGE)


@router.post(
    "",
    response_model=KotSendResponse,
    status_code=201,
    dependencies=[Depends(require_role("tenant_admin", "pos_user", "waiter", "pos_operator"))],
)
async def send_order_to_kot(
    payload: KotSendRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> KotSendResponse:
    await _require_kds_feature(db, current_user.tenant_id)
    tenant = await _get_tenant(db, current_user)
    result = await send_kot(db, tenant, payload.order_id)
    await db.commit()

    await ws_manager.broadcast(result.location_id, build_kot_ticket_broadcast(result))
    for stock_message in result.stock_messages:
        await ws_manager.broadcast(result.location_id, stock_message)

    return KotSendResponse(
        id=result.ticket.id,
        ticket_number=result.ticket.ticket_number,
        order_id=result.ticket.order_id,
        table_number=result.table_number,
        section_name_en=result.section_name_en,
        status=result.ticket.status,
        printed=result.printed,
        print_job=result.print_job,
        print_error=result.print_error,
    )


@router.get("/tickets/active", response_model=list[ActiveKotTicketResponse])
async def get_active_tickets(
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ActiveKotTicketResponse]:
    await _require_kds_feature(db, current_user.tenant_id)
    return await list_active_tickets(db, current_user.tenant_id, location_id)


@router.patch(
    "/tickets/{ticket_id}/status",
    response_model=ActiveKotTicketResponse,
    dependencies=[Depends(require_role("kitchen", "tenant_admin"))],
)
async def set_ticket_status(
    ticket_id: uuid.UUID,
    payload: KotTicketStatusUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveKotTicketResponse:
    await _require_kds_feature(db, current_user.tenant_id)
    ticket = await get_ticket_or_404(db, current_user.tenant_id, ticket_id)
    order = (await db.execute(select(Order).where(Order.id == ticket.order_id))).scalar_one()
    order_location_id = order.location_id

    ticket = await update_ticket_status(db, ticket, payload.status)

    # Built directly from this ticket/order rather than re-querying list_active_tickets
    # and searching for it — a ticket marked "ready" can legitimately have just aged
    # itself out of that active list (Guided POS's combined KOT+Bill route, where the
    # order is already billed and this ticket's only remaining visibility exception was
    # "not yet ready"), so a membership lookup would wrongly fail for exactly the update
    # that's supposed to succeed.
    updated = await build_active_ticket_response(db, ticket, order)
    await db.commit()

    await ws_manager.broadcast(
        order_location_id,
        {
            "type": "kot_ticket",
            "id": str(updated.id),
            "ticket_number": updated.ticket_number,
            "order_id": str(updated.order_id),
            "table_number": updated.table_number,
            "section_name_en": updated.section_name_en,
            "status": updated.status,
        },
    )
    return updated


@router.post(
    "/tickets/{ticket_id}/clear",
    response_model=ActiveKotTicketResponse,
    dependencies=[Depends(require_role("tenant_admin", "pos_user", "pos_operator"))],
)
async def clear_kot_ticket(
    ticket_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveKotTicketResponse:
    """Dismisses a "bill already printed" (order_billed_via_kot) ticket from the KOT
    Tickets screen/popup — same billing-role gate as the popup itself, distinct from
    `set_ticket_status` above which is Kitchen Display-only (kitchen/tenant_admin).
    """
    await _require_kds_feature(db, current_user.tenant_id)
    ticket = await get_ticket_or_404(db, current_user.tenant_id, ticket_id)
    order = (await db.execute(select(Order).where(Order.id == ticket.order_id))).scalar_one()
    order_location_id = order.location_id

    ticket = await clear_billed_ticket(db, ticket)
    updated = await build_active_ticket_response(db, ticket, order)
    await db.commit()

    await ws_manager.broadcast(
        order_location_id,
        {
            "type": "kot_ticket",
            "id": str(updated.id),
            "ticket_number": updated.ticket_number,
            "order_id": str(updated.order_id),
            "table_number": updated.table_number,
            "section_name_en": updated.section_name_en,
            "status": updated.status,
        },
    )
    return updated
