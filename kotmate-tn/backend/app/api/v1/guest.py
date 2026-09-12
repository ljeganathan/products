from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentGuest, require_guest_tenant_scope
from app.core.security import create_guest_token
from app.db.session import get_db
from app.models import SeatingSection
from app.schemas.categories import CategoryResponse
from app.schemas.guest import (
    GuestBillPreviewResponse,
    GuestCartUpdateRequest,
    GuestProfileUpdateRequest,
    GuestSessionResponse,
    RequestBillResponse,
)
from app.schemas.items import ItemResponse
from app.schemas.kot import ActiveKotTicketResponse, KotSendResponse
from app.schemas.orders import OrderResponse
from app.services.category_service import list_categories
from app.services.guest_service import (
    create_or_resume_session,
    get_cart,
    get_menu,
    get_order_status,
    get_top_sellers,
    place_takeaway_order,
    preview_guest_bill,
    request_bill,
    send_kot_for_guest,
    to_session_response,
    update_cart,
    update_profile,
)
from app.services.kot_service import build_kot_ticket_broadcast
from app.ws.manager import manager as ws_manager

# Genuinely public route (no CurrentUser, no CurrentGuest) — this *is* the guest
# "login", the qr_token itself is the credential. Every other route below depends on
# `require_guest_tenant_scope`, never on the staff `get_current_user`/`require_role` —
# the two auth worlds never mix (CLAUDE.md §5's usual RBAC separation, extended to a
# second, narrower guest identity for Phase 25).
router = APIRouter(prefix="/guest", tags=["guest"])


@router.post("/sessions/{qr_token}", response_model=GuestSessionResponse)
async def start_or_resume_guest_session(
    qr_token: str, db: AsyncSession = Depends(get_db)
) -> GuestSessionResponse:
    guest_session, tenant = await create_or_resume_session(db, qr_token)
    # Built *before* commit, not after: resolving a session's table/section name needs
    # `require_guest_tenant_scope`'s RLS context, and that's a `SET LOCAL` scoped to
    # this transaction only — a query issued after `db.commit()` ends that transaction
    # runs with no tenant context, so RLS would silently match zero rows instead of
    # this one (a real bug caught here: it surfaced as a 500 that the browser reported
    # as a bare "Network Error" since the response had no CORS headers on the way out).
    response = await to_session_response(db, guest_session)
    await db.commit()

    token = create_guest_token(
        guest_session_id=guest_session.id,
        tenant_id=tenant.id,
        location_id=guest_session.location_id,
        table_id=guest_session.table_id,
    )
    response.guest_token = token
    return response


@router.patch(
    "/sessions/me",
    response_model=GuestSessionResponse,
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def update_guest_profile(
    payload: GuestProfileUpdateRequest,
    guest: CurrentGuest = Depends(require_guest_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> GuestSessionResponse:
    guest_session = await update_profile(db, guest, payload)
    response = await to_session_response(db, guest_session)
    await db.commit()
    # No new token issued here — the guest is already holding a valid one; this route
    # only ever changes name/phone, never identity, so `guest_token` is left blank
    # rather than handing back a value that would misleadingly suggest a refresh.
    response.guest_token = ""
    return response


@router.get("/menu", response_model=list[ItemResponse], dependencies=[Depends(require_guest_tenant_scope)])
async def get_guest_menu(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> list[ItemResponse]:
    return await get_menu(db, guest)


@router.get(
    "/top-sellers",
    response_model=list[ItemResponse],
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def get_guest_top_sellers(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> list[ItemResponse]:
    """Backs the guest menu's "Top Selling" category tab (`CategoryNav` always
    renders one) — same rolling-window query the staff POS grid's own tab uses.
    """
    return await get_top_sellers(db, guest)


@router.get(
    "/categories",
    response_model=list[CategoryResponse],
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def get_guest_categories(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> list[CategoryResponse]:
    """Same listing the staff POS grid's `CategoryNav` already renders from — lets the
    guest menu group/filter by category the same way, instead of one long flat list.
    """
    return await list_categories(db, guest.tenant_id)


@router.get(
    "/cart",
    response_model=OrderResponse | None,
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def get_guest_cart(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> OrderResponse | None:
    """Rehydrates the cart on load/reload — `null` when nothing's been added yet."""
    return await get_cart(db, guest)


@router.post("/cart", response_model=OrderResponse, dependencies=[Depends(require_guest_tenant_scope)])
async def update_guest_cart(
    payload: GuestCartUpdateRequest,
    guest: CurrentGuest = Depends(require_guest_tenant_scope),
    db: AsyncSession = Depends(get_db),
) -> OrderResponse:
    result = await update_cart(db, guest, payload.items)
    await db.commit()
    return result


@router.post(
    "/send-kot",
    response_model=KotSendResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def guest_send_to_kitchen(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> KotSendResponse:
    if guest.table_id is None:
        # Takeaway: no real KOT ticket yet, nothing printed, no stock touched — see
        # `place_takeaway_order`'s own docstring for why. The order is already visible
        # to staff on the KOT Tickets screen as a pending row the moment it has items,
        # so there's nothing to broadcast here either.
        guest_session = await place_takeaway_order(db, guest)
        section = (
            await db.execute(select(SeatingSection).where(SeatingSection.id == guest_session.section_id))
        ).scalar_one()
        await db.commit()
        return KotSendResponse(
            id=guest_session.order_id,
            ticket_number=guest_session.pickup_token or "",
            order_id=guest_session.order_id,
            table_number=None,
            section_name_en=section.name_en,
            status="pending",
            printed=False,
        )

    result = await send_kot_for_guest(db, guest)
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


@router.get(
    "/order-status",
    response_model=list[ActiveKotTicketResponse],
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def get_guest_order_status(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> list[ActiveKotTicketResponse]:
    return await get_order_status(db, guest)


@router.get(
    "/bill-preview",
    response_model=GuestBillPreviewResponse,
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def get_guest_bill_preview(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> GuestBillPreviewResponse:
    return await preview_guest_bill(db, guest)


@router.post(
    "/request-bill",
    response_model=RequestBillResponse,
    dependencies=[Depends(require_guest_tenant_scope)],
)
async def guest_request_bill(
    guest: CurrentGuest = Depends(require_guest_tenant_scope), db: AsyncSession = Depends(get_db)
) -> RequestBillResponse:
    guest_session = await request_bill(db, guest)
    await db.commit()
    await ws_manager.broadcast(
        guest.location_id,
        {
            "type": "payment_claimed",
            "table_id": str(guest.table_id) if guest.table_id else None,
            "pickup_token": guest_session.pickup_token,
        },
    )
    return RequestBillResponse(status=guest_session.status)
