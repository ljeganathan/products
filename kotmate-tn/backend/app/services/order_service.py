import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser
from app.models import (
    Item,
    ItemSectionPrice,
    Order,
    OrderItem,
    SeatingSection,
    Table,
    TenantLocation,
    User,
    Waiter,
)
from app.schemas.orders import (
    OrderCreateRequest,
    OrderItemResponse,
    OrderLineInput,
    OrderPreviewResponse,
    OrderResponse,
    OrderUpdateRequest,
)
from app.services.waiter_service import get_waiter_by_user_id


@dataclass
class _LineData:
    item: Item
    unit_price: float
    quantity: int
    notes: str | None
    is_kot_sent: bool
    existing_id: uuid.UUID | None


async def _validate_location(session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID) -> None:
    exists = (
        await session.execute(
            select(TenantLocation.id).where(
                TenantLocation.id == location_id, TenantLocation.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "location_id does not belong to this tenant")


async def _get_section_or_400(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID
) -> SeatingSection:
    section = (
        await session.execute(
            select(SeatingSection).where(
                SeatingSection.id == section_id, SeatingSection.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if section is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "section_id does not belong to this tenant")
    return section


async def _get_table_or_400(session: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID) -> Table:
    table = (
        await session.execute(select(Table).where(Table.id == table_id, Table.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if table is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "table_id does not belong to this tenant")
    return table


async def _validate_table_matches_section(
    session: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID | None, section_id: uuid.UUID
) -> None:
    if table_id is None:
        return
    table = await _get_table_or_400(session, tenant_id, table_id)
    if table.section_id != section_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "table_id does not belong to the selected section_id"
        )


async def _get_waiter_or_400(session: AsyncSession, tenant_id: uuid.UUID, waiter_id: uuid.UUID) -> Waiter:
    waiter = (
        await session.execute(select(Waiter).where(Waiter.id == waiter_id, Waiter.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if waiter is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "waiter_id does not belong to this tenant")
    return waiter


async def _resolve_waiter_id(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    current_user: CurrentUser,
    requested_waiter_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """A `waiter` login is always auto-locked to their own linked Waiter Master row,
    ignoring whatever the client sent (defense-in-depth — the frontend also disables the
    selector for this role, CLAUDE.md §11). `pos_user`/`tenant_admin` may assign anyone.
    """
    if current_user.role == "waiter":
        own_waiter = await get_waiter_by_user_id(session, tenant_id, current_user.id)
        return own_waiter.id if own_waiter else None
    if requested_waiter_id is not None:
        await _get_waiter_or_400(session, tenant_id, requested_waiter_id)
    return requested_waiter_id


async def resolve_item_price(
    session: AsyncSession, tenant_id: uuid.UUID, item: Item, section_id: uuid.UUID
) -> float:
    override = (
        await session.execute(
            select(ItemSectionPrice.price).where(
                ItemSectionPrice.tenant_id == tenant_id,
                ItemSectionPrice.item_id == item.id,
                ItemSectionPrice.section_id == section_id,
            )
        )
    ).scalar_one_or_none()
    return float(override) if override is not None else float(item.price)


async def _get_item_or_400(session: AsyncSession, tenant_id: uuid.UUID, item_id: uuid.UUID) -> Item:
    item = (
        await session.execute(
            select(Item).where(Item.id == item_id, Item.tenant_id == tenant_id, Item.is_active.is_(True))
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more items are invalid or unavailable")
    return item


async def _new_line(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID, line_input: OrderLineInput
) -> _LineData:
    item = await _get_item_or_400(session, tenant_id, line_input.item_id)
    unit_price = await resolve_item_price(session, tenant_id, item, section_id)
    return _LineData(
        item=item,
        unit_price=unit_price,
        quantity=line_input.quantity,
        notes=line_input.notes,
        is_kot_sent=False,
        existing_id=None,
    )


async def _repriced_line(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID, existing: OrderItem
) -> _LineData:
    item = (
        await session.execute(select(Item).where(Item.id == existing.item_id))
    ).scalar_one()
    unit_price = await resolve_item_price(session, tenant_id, item, section_id)
    return _LineData(
        item=item,
        unit_price=unit_price,
        quantity=existing.quantity,
        notes=existing.notes,
        is_kot_sent=existing.is_kot_sent,
        existing_id=existing.id,
    )


def _line_response(line: _LineData) -> OrderItemResponse:
    return OrderItemResponse(
        id=line.existing_id,
        item_id=line.item.id,
        name_en=line.item.name_en,
        name_ta=line.item.name_ta,
        item_code=line.item.item_code,
        unit_price=line.unit_price,
        quantity=line.quantity,
        notes=line.notes,
        is_kot_sent=line.is_kot_sent,
        line_total=round(line.unit_price * line.quantity, 2),
        track_inventory=line.item.track_inventory,
        available_qty=line.item.available_qty,
    )


def _incentive_amount(rate: float | None, subtotal: float) -> float | None:
    if rate is None:
        return None
    return round(float(rate) * subtotal / 100, 2)


async def _build_response(
    session: AsyncSession, order: Order, lines: list[_LineData]
) -> OrderResponse:
    section = (
        await session.execute(select(SeatingSection).where(SeatingSection.id == order.section_id))
    ).scalar_one()
    table = (
        (await session.execute(select(Table).where(Table.id == order.table_id))).scalar_one()
        if order.table_id
        else None
    )
    waiter = (
        (await session.execute(select(Waiter).where(Waiter.id == order.waiter_id))).scalar_one()
        if order.waiter_id
        else None
    )
    pos_user = (await session.execute(select(User).where(User.id == order.pos_user_id))).scalar_one()

    subtotal = round(sum(line.unit_price * line.quantity for line in lines), 2)

    return OrderResponse(
        id=order.id,
        location_id=order.location_id,
        section_id=order.section_id,
        section_name_en=section.name_en,
        section_is_seating=section.is_seating,
        table_id=order.table_id,
        table_number=table.table_number if table else None,
        waiter_id=order.waiter_id,
        waiter_name=waiter.name if waiter else None,
        pos_user_id=order.pos_user_id,
        pos_user_login_id=pos_user.user_id,
        status=order.status,
        hold_label=order.hold_label,
        party_label=order.party_label,
        items=[_line_response(line) for line in lines],
        subtotal=subtotal,
        waiter_incentive_amount=_incentive_amount(waiter.incentive_rate if waiter else None, subtotal),
        cashier_incentive_amount=_incentive_amount(pos_user.incentive_rate, subtotal),
        created_at=order.created_at,
    )


async def _load_lines(session: AsyncSession, order: Order) -> list[_LineData]:
    # Ordered explicitly — an UPDATE (e.g. a quantity change) gives a row a new physical
    # tuple version, so an unordered scan of this table can silently return a different
    # row order after any edit, making cart lines appear to reshuffle on screen even
    # though nothing about their logical position changed (production feedback).
    # `line_no` is the real, explicit ordering (set once at insert, see create_order/
    # apply_line_changes); `created_at`/`id` are just deterministic tiebreaks for the
    # pre-line_no rows every existing order already has (they all backfilled to 0).
    order_items = (
        await session.execute(
            select(OrderItem)
            .where(OrderItem.order_id == order.id)
            .order_by(OrderItem.line_no, OrderItem.created_at, OrderItem.id)
        )
    ).scalars().all()
    lines = []
    for oi in order_items:
        item = (await session.execute(select(Item).where(Item.id == oi.item_id))).scalar_one()
        lines.append(
            _LineData(
                item=item,
                unit_price=float(oi.unit_price),
                quantity=oi.quantity,
                notes=oi.notes,
                is_kot_sent=oi.is_kot_sent,
                existing_id=oi.id,
            )
        )
    return lines


async def create_order(
    session: AsyncSession, tenant_id: uuid.UUID, current_user: CurrentUser, req: OrderCreateRequest
) -> OrderResponse:
    await _validate_location(session, tenant_id, req.location_id)
    await _get_section_or_400(session, tenant_id, req.section_id)
    await _validate_table_matches_section(session, tenant_id, req.table_id, req.section_id)
    waiter_id = await _resolve_waiter_id(session, tenant_id, current_user, req.waiter_id)

    order = Order(
        tenant_id=tenant_id,
        location_id=req.location_id,
        section_id=req.section_id,
        table_id=req.table_id,
        waiter_id=waiter_id,
        pos_user_id=current_user.id,
        status="open",
        hold_label=req.hold_label,
        party_label=req.party_label,
    )
    session.add(order)
    await session.flush()

    lines = [await _new_line(session, tenant_id, req.section_id, line_in) for line_in in req.items]
    for line_no, line in enumerate(lines):
        session.add(
            OrderItem(
                tenant_id=tenant_id,
                order_id=order.id,
                item_id=line.item.id,
                unit_price=line.unit_price,
                quantity=line.quantity,
                notes=line.notes,
                is_kot_sent=False,
                line_no=line_no,
            )
        )
    await session.flush()

    return await build_order_response(session, order)


async def get_order_or_404(session: AsyncSession, tenant_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = (
        await session.execute(select(Order).where(Order.id == order_id, Order.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
    return order


async def list_orders(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    status_filter: str | None,
    location_id: uuid.UUID | None,
    table_id: uuid.UUID | None = None,
) -> list[Order]:
    query = select(Order).where(Order.tenant_id == tenant_id)
    if status_filter is not None:
        query = query.where(Order.status == status_filter)
    if location_id is not None:
        query = query.where(Order.location_id == location_id)
    if table_id is not None:
        query = query.where(Order.table_id == table_id)
    rows = await session.execute(query.order_by(Order.updated_at.desc()))
    return list(rows.scalars().all())


async def compute_updated_lines(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    order: Order,
    target_section_id: uuid.UUID,
    items_input: list[OrderLineInput] | None,
) -> list[_LineData]:
    """Pure computation, no persistence — shared by the dry-run preview and the real
    apply path so they can never drift apart.

    When `items_input` is given (a cart replace — add/remove/quantity edit), each input
    line is matched back to its exact `OrderItem` row by `line_in.id` (echoed from the
    last response) whenever the client provided one, so an edit that doesn't touch a
    given line keeps that row's identity rather than deleting and recreating it — Phase
    08's `kot_ticket_items` FKs to these ids, so an already-fired line surviving an
    unrelated cart edit must not silently get a new id.

    An input line with `id=None` always becomes a brand-new row, even if its item_id/
    notes happen to match an existing one — this is what makes "add one more of an item
    that's already been sent to the kitchen" work correctly: the POS client (POSPage.tsx's
    handleAddItem) only reuses an *unsent* existing line's id when bumping a quantity, so
    an add-on ordered after the first KOT ticket always lands in a fresh, still-unsent
    line instead of silently inflating the already-fired row's quantity — which would
    have left the kitchen never finding out about the extra portion, since kot_service.
    send_kot only re-fires rows where is_kot_sent is still false (production feedback:
    "again i am ordering dosai for the same table but its not adding").

    A `line_in.id` with no matching row (e.g. stale client state) falls back to matching
    by (item_id, notes) among rows no id-based match has already claimed, preferring an
    unsent one — purely defensive, since every current caller always supplies an id for
    an existing line.
    """
    if items_input is not None:
        existing_rows = list(
            (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars()
        )
        by_id = {row.id: row for row in existing_rows}
        unmatched = list(existing_rows)
        lines: list[_LineData] = []
        for line_in in items_input:
            match = by_id.get(line_in.id) if line_in.id is not None else None
            if match is not None and match not in unmatched:
                match = None  # already claimed by an earlier input line with the same id
            if match is None and line_in.id is None:
                # No id supplied — fall back to a fuzzy match, preferring a not-yet-sent
                # row so an id-less caller can't accidentally inflate an already-fired line.
                candidates = [
                    r for r in unmatched if r.item_id == line_in.item_id and r.notes == line_in.notes
                ]
                match = next(
                    (r for r in candidates if not r.is_kot_sent),
                    candidates[0] if candidates else None,
                )
            item = await _get_item_or_400(session, tenant_id, line_in.item_id)
            unit_price = await resolve_item_price(session, tenant_id, item, target_section_id)
            if match is not None:
                unmatched.remove(match)
                lines.append(
                    _LineData(
                        item=item,
                        unit_price=unit_price,
                        quantity=line_in.quantity,
                        notes=line_in.notes,
                        is_kot_sent=match.is_kot_sent,
                        existing_id=match.id,
                    )
                )
            else:
                lines.append(
                    _LineData(
                        item=item,
                        unit_price=unit_price,
                        quantity=line_in.quantity,
                        notes=line_in.notes,
                        is_kot_sent=False,
                        existing_id=None,
                    )
                )
        return lines

    existing_lines = await _load_lines(session, order)
    if target_section_id == order.section_id:
        return existing_lines
    return [
        await _repriced_line(session, tenant_id, target_section_id, oi)
        for oi in (
            await session.execute(
                select(OrderItem)
                .where(OrderItem.order_id == order.id)
                .order_by(OrderItem.line_no, OrderItem.created_at, OrderItem.id)
            )
        ).scalars()
    ]


async def apply_line_changes(
    session: AsyncSession, tenant_id: uuid.UUID, order: Order, lines: list[_LineData]
) -> None:
    """Reconciles `order_items` against the computed `lines`, updating matched rows
    in place (preserving their id) and only inserting/deleting where a line is
    genuinely new or genuinely gone — see `compute_updated_lines` for why identity
    matters here.
    """
    existing_rows = {
        oi.id: oi
        for oi in (await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))).scalars()
    }
    keep_ids: set[uuid.UUID] = set()
    # A brand-new line is always appended after everything already in the cart, never
    # interleaved — matches how a cashier actually experiences "add one more" (POSPage.
    # tsx's handleAddItem), and keeps every existing line's own line_no untouched.
    next_line_no = max((row.line_no for row in existing_rows.values()), default=-1) + 1

    for line in lines:
        if line.existing_id is not None and line.existing_id in existing_rows:
            row = existing_rows[line.existing_id]
            row.unit_price = line.unit_price
            row.quantity = line.quantity
            row.notes = line.notes
            keep_ids.add(row.id)
        else:
            session.add(
                OrderItem(
                    tenant_id=tenant_id,
                    order_id=order.id,
                    item_id=line.item.id,
                    unit_price=line.unit_price,
                    quantity=line.quantity,
                    notes=line.notes,
                    is_kot_sent=line.is_kot_sent,
                    line_no=next_line_no,
                )
            )
            next_line_no += 1

    stale_ids = [row_id for row_id in existing_rows if row_id not in keep_ids]
    if stale_ids:
        await session.execute(delete(OrderItem).where(OrderItem.id.in_(stale_ids)))
    await session.flush()


async def build_order_response(session: AsyncSession, order: Order) -> OrderResponse:
    """Public entry point for rendering a persisted order — loads its current lines and
    builds the full response in one call, for routes that just need "the order as it
    is right now" (create/get/list/apply-update).
    """
    lines = await _load_lines(session, order)
    return await _build_response(session, order, lines)


async def _resolve_target_section_and_table(
    session: AsyncSession, tenant_id: uuid.UUID, order: Order, data: dict
) -> tuple[uuid.UUID, uuid.UUID | None]:
    target_section_id = data.get("section_id", order.section_id)
    target_table_id = data["table_id"] if "table_id" in data else order.table_id
    await _get_section_or_400(session, tenant_id, target_section_id)
    await _validate_table_matches_section(session, tenant_id, target_table_id, target_section_id)
    return target_section_id, target_table_id


async def preview_order_update(
    session: AsyncSession, tenant_id: uuid.UUID, order: Order, req: OrderUpdateRequest
) -> OrderPreviewResponse:
    """Read-only — computes what the order would look like after `req` without
    persisting anything, so the frontend can confirm a table/section change's
    recalculated totals with the user before committing to it.
    """
    data = req.model_dump(exclude_unset=True)
    target_section_id, target_table_id = await _resolve_target_section_and_table(
        session, tenant_id, order, data
    )

    before_lines = await _load_lines(session, order)
    after_lines = await compute_updated_lines(session, tenant_id, order, target_section_id, req.items)

    before_subtotal = round(sum(li.unit_price * li.quantity for li in before_lines), 2)
    after_subtotal = round(sum(li.unit_price * li.quantity for li in after_lines), 2)

    shell = Order(
        id=order.id,
        tenant_id=order.tenant_id,
        location_id=order.location_id,
        section_id=target_section_id,
        table_id=target_table_id,
        waiter_id=data.get("waiter_id", order.waiter_id),
        pos_user_id=order.pos_user_id,
        status=data.get("status", order.status),
        hold_label=data.get("hold_label", order.hold_label),
        party_label=data.get("party_label", order.party_label),
    )
    shell.created_at = order.created_at

    preview = await _build_response(session, shell, after_lines)
    return OrderPreviewResponse(order=preview, subtotal_changed=before_subtotal != after_subtotal)


async def apply_order_update(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    current_user: CurrentUser,
    order: Order,
    req: OrderUpdateRequest,
) -> OrderResponse:
    """Persists `req` onto `order` — table/section/waiter/hold_label/status plus a cart
    replace or section-driven reprice of the existing lines. Caller commits.
    """
    data = req.model_dump(exclude_unset=True)
    target_section_id, target_table_id = await _resolve_target_section_and_table(
        session, tenant_id, order, data
    )
    lines = await compute_updated_lines(session, tenant_id, order, target_section_id, req.items)

    order.section_id = target_section_id
    order.table_id = target_table_id
    if "waiter_id" in data or current_user.role == "waiter":
        order.waiter_id = await _resolve_waiter_id(
            session, tenant_id, current_user, data.get("waiter_id")
        )
    if "hold_label" in data:
        order.hold_label = data["hold_label"]
    if "party_label" in data:
        order.party_label = data["party_label"]
    if "status" in data:
        order.status = data["status"]
    # Picking up/editing an order as pos_user, pos_operator, or tenant_admin makes them
    # the cashier-of-record from that point on (CLAUDE.md §11) — a waiter's own edits
    # never reassign it away from whoever already claimed it.
    if current_user.role in ("pos_user", "tenant_admin", "pos_operator"):
        order.pos_user_id = current_user.id

    await apply_line_changes(session, tenant_id, order, lines)
    return await build_order_response(session, order)
