import base64
import uuid
from dataclasses import dataclass, field

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    HotelMaster,
    Item,
    KotTicket,
    KotTicketItem,
    Order,
    OrderItem,
    Printer,
    SeatingSection,
    Table,
    Tenant,
)
from app.printing.base import KotTicketLine, KotTicketRenderData
from app.printing.dispatcher import dispatch_kot_print
from app.printing.network_transport import send_raw_bytes_over_network
from app.schemas.kot import ActiveKotTicketItem, ActiveKotTicketResponse
from app.schemas.printing import PrintJobPayload
from app.services.item_service import LOW_STOCK_THRESHOLD
from app.services.order_service import get_order_or_404
from app.services.stock_service import is_stock_tracking_enabled, set_item_stock
from app.services.tenant_onboarding import get_active_plan


@dataclass
class KotSendResult:
    ticket: KotTicket
    location_id: uuid.UUID
    table_number: str | None
    section_name_en: str
    printed: bool
    stock_messages: list[dict] = field(default_factory=list)
    # Populated only for a `usb`/`local_agent` KOT printer — see PrintJobPayload.
    print_job: PrintJobPayload | None = None
    # Set only for a `network`/`wifi` KOT printer the backend tried and failed to reach.
    print_error: str | None = None


async def _next_ticket_number(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    count = (
        await session.execute(
            select(func.count()).select_from(KotTicket).where(KotTicket.tenant_id == tenant_id)
        )
    ).scalar_one()
    return f"T{count + 1}"


async def _load_section_and_table(
    session: AsyncSession, order: Order
) -> tuple[SeatingSection, Table | None]:
    section = (
        await session.execute(select(SeatingSection).where(SeatingSection.id == order.section_id))
    ).scalar_one()
    table = (
        (await session.execute(select(Table).where(Table.id == order.table_id))).scalar_one()
        if order.table_id
        else None
    )
    return section, table


async def send_kot(
    session: AsyncSession, tenant: Tenant, order_id: uuid.UUID
) -> KotSendResult:
    """Fires a ticket for every not-yet-sent line on the order (supports repeat-KOT —
    add-on items ordered after the first ticket only send what's new, CLAUDE.md
    Phase 08 scope) and decrements stock for tracked items.
    """
    order = await get_order_or_404(session, tenant.id, order_id)
    if order.status == "billed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This order has already been billed")

    unsent = (
        await session.execute(
            select(OrderItem).where(OrderItem.order_id == order.id, OrderItem.is_kot_sent.is_(False))
        )
    ).scalars().all()
    if not unsent:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No new items to send to the kitchen")

    section, table = await _load_section_and_table(session, order)

    # Fetched once here (not per-item) — reused below for the stock-deduction gate and
    # the printing gate, so this only queries the active plan once per KOT send.
    plan = await get_active_plan(session, tenant.id)
    stock_tracking = is_stock_tracking_enabled(tenant, plan.features if plan else None)

    ticket_number = await _next_ticket_number(session, tenant.id)
    ticket = KotTicket(tenant_id=tenant.id, order_id=order.id, ticket_number=ticket_number, status="new")
    session.add(ticket)
    await session.flush()

    render_lines: list[KotTicketLine] = []
    stock_messages: list[dict] = []

    for order_item in unsent:
        item = (await session.execute(select(Item).where(Item.id == order_item.item_id))).scalar_one()
        session.add(
            KotTicketItem(
                tenant_id=tenant.id,
                kot_ticket_id=ticket.id,
                order_item_id=order_item.id,
                quantity=order_item.quantity,
            )
        )
        order_item.is_kot_sent = True
        render_lines.append(
            KotTicketLine(
                name_en=item.name_en,
                name_ta=item.name_ta,
                quantity=order_item.quantity,
                notes=order_item.notes,
            )
        )

        if item.track_inventory and stock_tracking:
            new_qty = max(0, (item.available_qty or 0) - order_item.quantity)
            await set_item_stock(
                session,
                tenant.id,
                item,
                new_qty,
                "kot_deduction",
                location_id=order.location_id,
                reference_order_id=order.id,
            )
            stock_messages.append(
                {
                    "type": "item_stock",
                    "item_id": str(item.id),
                    "available_qty": new_qty,
                    "low_stock": new_qty <= LOW_STOCK_THRESHOLD,
                    "out_of_stock": new_qty <= 0,
                }
            )

    await session.flush()

    # Physical printing is plan-gated (Lite = on-screen ticket only, CLAUDE.md §6) and
    # only fires when the tenant has actually registered a KOT printer for this location.
    printed = False
    print_job: PrintJobPayload | None = None
    print_error: str | None = None
    if plan and plan.features.get("kot_printing"):
        printer = (
            await session.execute(
                select(Printer).where(
                    Printer.tenant_id == tenant.id,
                    Printer.location_id == order.location_id,
                    Printer.target == "kot",
                    Printer.is_active.is_(True),
                )
            )
        ).scalars().first()
        if printer is not None:
            hotel = (
                await session.execute(
                    select(HotelMaster).where(HotelMaster.location_id == order.location_id)
                )
            ).scalar_one_or_none()
            render_data = KotTicketRenderData(
                ticket_number=ticket.ticket_number,
                table_number=table.table_number if table else None,
                section_name_en=section.name_en,
                created_at=ticket.created_at,
                lines=render_lines,
                show_tamil_names=hotel.show_tamil_names if hotel else True,
                party_label=order.party_label,
                paper_width_mm=printer.paper_width_mm,
            )
            content = dispatch_kot_print(printer, render_data)
            # "usb"/"local_agent" KOT printers are physically attached to the counter
            # machine, not this backend container — hand the rendered bytes back to the
            # frontend so it can push them to the local print-agent/WebUSB, same as bill
            # printing (bill_service.py's _dispatch_print_for_bill). "network"/"wifi"
            # printers are reachable directly from here over the LAN, so the backend
            # sends the raw bytes itself instead of claiming success and doing nothing.
            if printer.connection_type in ("usb", "local_agent"):
                print_job = PrintJobPayload(
                    printer_id=printer.id,
                    connection_type=printer.connection_type,
                    connection_details=printer.connection_details or {},
                    data_base64=base64.b64encode(content).decode("ascii"),
                )
                printed = True
            elif printer.connection_type in ("network", "wifi"):
                details = printer.connection_details or {}
                print_error = send_raw_bytes_over_network(details.get("ip_address"), details.get("port"), content)
                printed = print_error is None
            else:
                print_error = f"{printer.connection_type.replace('_', ' ').title()} printing isn't supported yet."

    return KotSendResult(
        ticket=ticket,
        location_id=order.location_id,
        table_number=table.table_number if table else None,
        section_name_en=section.name_en,
        printed=printed,
        stock_messages=stock_messages,
        print_job=print_job,
        print_error=print_error,
    )


async def get_ticket_or_404(session: AsyncSession, tenant_id: uuid.UUID, ticket_id: uuid.UUID) -> KotTicket:
    ticket = (
        await session.execute(
            select(KotTicket).where(KotTicket.id == ticket_id, KotTicket.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if ticket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "KOT ticket not found")
    return ticket


async def update_ticket_status(session: AsyncSession, ticket: KotTicket, new_status: str) -> KotTicket:
    ticket.status = new_status
    await session.flush()
    return ticket


async def _ticket_response(session: AsyncSession, ticket: KotTicket, order: Order) -> ActiveKotTicketResponse:
    section, table = await _load_section_and_table(session, order)
    rows = (
        await session.execute(
            select(KotTicketItem, OrderItem, Item)
            .join(OrderItem, OrderItem.id == KotTicketItem.order_item_id)
            .join(Item, Item.id == OrderItem.item_id)
            .where(KotTicketItem.kot_ticket_id == ticket.id)
        )
    ).all()
    items = [
        ActiveKotTicketItem(name_en=item.name_en, name_ta=item.name_ta, quantity=kti.quantity)
        for kti, _oi, item in rows
    ]
    return ActiveKotTicketResponse(
        id=ticket.id,
        ticket_number=ticket.ticket_number,
        order_id=order.id,
        table_number=table.table_number if table else None,
        party_label=order.party_label,
        section_name_en=section.name_en,
        status=ticket.status,
        created_at=ticket.created_at,
        items=items,
    )


async def list_active_tickets(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None
) -> list[ActiveKotTicketResponse]:
    """Every ticket whose parent order isn't billed yet — the same query backs both the
    Kitchen Display and the POS billing screen's "KOT Tickets" popup (CLAUDE.md §11), so
    a ticket disappears from both the instant its order is billed, with no extra
    client-side bookkeeping.
    """
    query = (
        select(KotTicket, Order)
        .join(Order, Order.id == KotTicket.order_id)
        .where(KotTicket.tenant_id == tenant_id, Order.status != "billed")
    )
    if location_id is not None:
        query = query.where(Order.location_id == location_id)
    rows = (await session.execute(query.order_by(KotTicket.created_at.desc()))).all()
    return [await _ticket_response(session, ticket, order) for ticket, order in rows]


def build_kot_ticket_broadcast(result: KotSendResult) -> dict:
    return {
        "type": "kot_ticket",
        "id": str(result.ticket.id),
        "ticket_number": result.ticket.ticket_number,
        "order_id": str(result.ticket.order_id),
        "table_number": result.table_number,
        "section_name_en": result.section_name_en,
        "status": result.ticket.status,
    }
