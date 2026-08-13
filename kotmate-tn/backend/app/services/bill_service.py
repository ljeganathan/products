import base64
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import CurrentUser
from app.models import (
    AuditLog,
    Bill,
    BillItem,
    HotelMaster,
    Item,
    Order,
    OrderItem,
    Payment,
    Printer,
    SeatingSection,
    Table,
    TaxRule,
    Tenant,
    TenantLocation,
    User,
    Waiter,
)
from app.printing.base import BillLine, BillRenderData
from app.printing.dispatcher import dispatch_bill_print
from app.printing.network_transport import send_raw_bytes_over_network
from app.schemas.bills import (
    BillCreateRequest,
    BillItemResponse,
    BillPreviewRequest,
    BillPreviewResponse,
    BillResponse,
    BillSearchParams,
    PaymentResponse,
)
from app.schemas.printing import PrintJobPayload
from app.services.discount_rule_service import (
    get_active_coupon,
    get_active_item_level_rules,
    get_best_active_flat_rule,
    rule_amount,
)
from app.services.order_service import get_order_or_404
from app.services.stock_service import is_stock_tracking_enabled, set_item_stock
from app.services.tax_rule_service import get_default_tax_rule
from app.services.tenant_onboarding import get_active_plan

# Any discount above this rupee amount is written to audit_log for loss-prevention
# review (CLAUDE.md §11: "manual price override or discount applied above a
# configurable threshold"). Module constant for now, matching kot_service's
# `_LOW_STOCK_THRESHOLD` precedent — not yet a tenant-configurable setting.
_AUDIT_DISCOUNT_THRESHOLD = 500.0

_PAYMENT_AMOUNT_TOLERANCE = 0.01


@dataclass
class _PricedItem:
    order_item_id: uuid.UUID
    item: Item
    unit_price: float
    quantity: int
    line_total: float
    # Whether this line was ever sent to KOT — items billed directly (never sent to the
    # kitchen) still need a stock deduction at finalize time, since kot_service.send_kot
    # is normally the only place that decrements (see _deduct_stock_for_unsent_items).
    is_kot_sent: bool


@dataclass
class _BillTotals:
    priced_items: list[_PricedItem]
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    # subtotal - discount, pre-tax — the incentive base per CLAUDE.md §11 ("net sale
    # value, post-discount, pre-tax"), deliberately different from the live cart-screen
    # estimate in order_service (which has no discount to subtract yet at that point).
    net_taxable_value: float


def _round_half_up_rupee(value: float) -> int:
    """Currency round-half-up to the nearest rupee — Python's builtin `round()` uses
    banker's rounding (round-half-to-even), which would silently disagree with the
    ₹0.50-rounds-up convention a printed bill and a customer checking it both expect.
    """
    return int(value + 0.5) if value >= 0 else -int(-value + 0.5)


async def _load_priced_items(session: AsyncSession, order: Order) -> list[_PricedItem]:
    order_items = (
        await session.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    ).scalars().all()
    if not order_items:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot bill an order with no items")
    priced = []
    for oi in order_items:
        item = (await session.execute(select(Item).where(Item.id == oi.item_id))).scalar_one()
        priced.append(
            _PricedItem(
                order_item_id=oi.id,
                item=item,
                unit_price=float(oi.unit_price),
                quantity=oi.quantity,
                line_total=round(float(oi.unit_price) * oi.quantity, 2),
                is_kot_sent=oi.is_kot_sent,
            )
        )
    return priced


async def _deduct_stock_for_unsent_items(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    plan_features: dict,
    order: Order,
    bill_id: uuid.UUID,
    priced_items: list[_PricedItem],
) -> None:
    """Stock normally decrements at KOT-send (kot_service.send_kot) — but a cashier can
    finalize a bill directly from the cart without ever sending it to the kitchen (a
    quick walk-in sale), and those lines would otherwise never decrement. This covers
    exactly that gap: only lines that were never KOT-sent get deducted here, so a line
    already decremented at KOT-send is never double-deducted.
    """
    tenant = (await session.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
    if not is_stock_tracking_enabled(tenant, plan_features):
        return
    for priced in priced_items:
        if priced.is_kot_sent or not priced.item.track_inventory:
            continue
        new_qty = max(0, (priced.item.available_qty or 0) - priced.quantity)
        await set_item_stock(
            session,
            tenant_id,
            priced.item,
            new_qty,
            "bill_deduction",
            location_id=order.location_id,
            reference_bill_id=bill_id,
        )


async def _compute_discount(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    plan_features: dict,
    priced_items: list[_PricedItem],
    subtotal: float,
    coupon_code: str | None,
) -> tuple[float, str | None]:
    """Item-level, flat, and coupon discounts all auto-resolve from currently-active,
    non-expired `discount_rules` (Phase 23) and stack — each one computed against
    whatever's left after the previous ones, so `discount_amount` is naturally capped at
    `subtotal` without a separate clamp. The cashier's only input is an optional coupon
    code; item-level and flat apply themselves whenever a matching rule is active.
    """
    allowed_types = plan_features.get("discount_types", ["flat_percent"])
    notes: list[str] = []
    total = 0.0

    if "item_level" in allowed_types:
        rules_by_item = await get_active_item_level_rules(
            session, tenant_id, {p.item.id for p in priced_items}
        )
        for priced in priced_items:
            rule = rules_by_item.get(priced.item.id)
            if rule is None:
                continue
            amount = round(min(rule_amount(rule, priced.line_total), priced.line_total), 2)
            if amount > 0:
                total += amount
                notes.append(f"{rule.name}: -₹{amount:.2f}")

    if "flat_percent" in allowed_types:
        remainder = subtotal - total
        rule = await get_best_active_flat_rule(session, tenant_id, remainder)
        if rule is not None:
            amount = round(min(rule_amount(rule, remainder), remainder), 2)
            if amount > 0:
                total += amount
                notes.append(f"{rule.name}: -₹{amount:.2f}")

    if coupon_code:
        if "coupon" not in allowed_types:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Coupons aren't available on your current plan")
        rule = await get_active_coupon(session, tenant_id, coupon_code)
        if rule is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid, inactive, or expired coupon code")
        remainder = subtotal - total
        amount = round(min(rule_amount(rule, remainder), remainder), 2)
        if amount > 0:
            total += amount
            notes.append(f"{rule.name}: -₹{amount:.2f}")

    return round(total, 2), "; ".join(notes) if notes else None


async def _resolve_line_tax_rule(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    tax_mode: str,
    priced: _PricedItem,
    default_rule: TaxRule | None,
    overrides: dict[uuid.UUID, uuid.UUID],
) -> TaxRule | None:
    if tax_mode == "single_rate":
        return default_rule

    override_id = overrides.get(priced.order_item_id)
    if override_id is not None:
        rule = (
            await session.execute(
                select(TaxRule).where(TaxRule.id == override_id, TaxRule.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if rule is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "line_tax_overrides references an unknown tax_rule_id"
            )
        return rule

    if priced.item.tax_class_id is not None:
        rule = (
            await session.execute(
                select(TaxRule).where(
                    TaxRule.id == priced.item.tax_class_id, TaxRule.tenant_id == tenant_id
                )
            )
        ).scalar_one_or_none()
        if rule is not None:
            return rule
    return default_rule


async def _compute_totals(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    plan_features: dict,
    priced_items: list[_PricedItem],
    coupon_code: str | None,
    line_tax_overrides: dict[uuid.UUID, uuid.UUID] | None,
) -> tuple[_BillTotals, str | None]:
    subtotal = round(sum(p.line_total for p in priced_items), 2)
    discount_amount, discount_note = await _compute_discount(
        session, tenant_id, plan_features, priced_items, subtotal, coupon_code
    )
    discount_amount = min(discount_amount, subtotal)
    net_taxable_value = round(subtotal - discount_amount, 2)

    tax_mode = plan_features.get("tax_mode", "single_rate")
    overrides = line_tax_overrides or {}
    if overrides and tax_mode != "multi_rate_per_item":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Per-item tax overrides require the multi_rate_per_item plan tier (Pro Max)",
        )
    default_rule = await get_default_tax_rule(session, tenant_id)

    # Discount is pro-rated across lines (proportional to each line's share of the
    # subtotal) so a per-item tax rate still applies to the correct post-discount base —
    # standard Indian billing practice, and the only way "multi-rate" tax and a
    # bill-level discount can coexist without double-taxing the discounted portion.
    discount_ratio = (discount_amount / subtotal) if subtotal > 0 else 0.0

    cgst_total = 0.0
    sgst_total = 0.0
    for priced in priced_items:
        rule = await _resolve_line_tax_rule(session, tenant_id, tax_mode, priced, default_rule, overrides)
        taxable_line = priced.line_total * (1 - discount_ratio)
        if rule is not None:
            cgst_total += taxable_line * float(rule.cgst_rate) / 100
            sgst_total += taxable_line * float(rule.sgst_rate) / 100

    cgst_amount = round(cgst_total, 2)
    sgst_amount = round(sgst_total, 2)

    pre_round_total = net_taxable_value + cgst_amount + sgst_amount
    grand_total = float(_round_half_up_rupee(pre_round_total))
    round_off_amount = round(grand_total - pre_round_total, 2)

    totals = _BillTotals(
        priced_items=priced_items,
        subtotal=subtotal,
        discount_amount=discount_amount,
        cgst_amount=cgst_amount,
        sgst_amount=sgst_amount,
        round_off_amount=round_off_amount,
        grand_total=grand_total,
        net_taxable_value=net_taxable_value,
    )
    return totals, discount_note


def _incentive_amount(rate: float | None, net_taxable_value: float) -> float | None:
    if rate is None:
        return None
    return round(float(rate) * net_taxable_value / 100, 2)


def _item_response(priced: _PricedItem) -> BillItemResponse:
    return BillItemResponse(
        id=None,
        item_id=priced.item.id,
        name_en=priced.item.name_en,
        name_ta=priced.item.name_ta,
        unit_price=priced.unit_price,
        quantity=priced.quantity,
        line_total=priced.line_total,
    )


async def _next_bill_number(session: AsyncSession, tenant_id: uuid.UUID) -> str:
    count = (
        await session.execute(select(func.count()).select_from(Bill).where(Bill.tenant_id == tenant_id))
    ).scalar_one()
    return f"B{count + 1}"


async def preview_bill(
    session: AsyncSession, tenant_id: uuid.UUID, req: BillPreviewRequest
) -> BillPreviewResponse:
    order = await get_order_or_404(session, tenant_id, req.order_id)
    if order.status == "billed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This order has already been billed")

    plan = await get_active_plan(session, tenant_id)
    plan_features = plan.features if plan else {}
    priced_items = await _load_priced_items(session, order)
    overrides = {uuid.UUID(k): v for k, v in (req.line_tax_overrides or {}).items()}
    totals, discount_note = await _compute_totals(
        session, tenant_id, plan_features, priced_items, req.coupon_code, overrides
    )

    waiter = (
        (await session.execute(select(Waiter).where(Waiter.id == order.waiter_id))).scalar_one()
        if order.waiter_id
        else None
    )
    pos_user = (await session.execute(select(User).where(User.id == order.pos_user_id))).scalar_one()

    return BillPreviewResponse(
        order_id=order.id,
        items=[_item_response(p) for p in totals.priced_items],
        subtotal=totals.subtotal,
        discount_amount=totals.discount_amount,
        discount_note=discount_note,
        cgst_amount=totals.cgst_amount,
        sgst_amount=totals.sgst_amount,
        round_off_amount=totals.round_off_amount,
        grand_total=totals.grand_total,
        waiter_incentive_amount=_incentive_amount(
            waiter.incentive_rate if waiter else None, totals.net_taxable_value
        ),
        cashier_incentive_amount=_incentive_amount(pos_user.incentive_rate, totals.net_taxable_value),
        payments=[],
    )


# Printed centered near the end of every bill unless the tenant has set their own
# `hotel_master.receipt_footer_message` in Settings (printer fixes batch).
_DEFAULT_RECEIPT_FOOTER_MESSAGE = "Thank You & Visit Again..!!!"


def _read_uploaded_file(url: str | None) -> bytes | None:
    """Resolves a URL previously returned by `storage.save` (e.g.
    `hotel_master.logo_url`, always `{UPLOAD_URL_PREFIX}/{tenant_id}/{subfolder}/...`)
    back to bytes on local disk. Returns None for anything that doesn't resolve — a
    missing/corrupt logo file should never break bill printing, just fall back to the
    no-logo rendering path.
    """
    if not url:
        return None
    settings = get_settings()
    prefix = settings.UPLOAD_URL_PREFIX.rstrip("/") + "/"
    if not url.startswith(prefix):
        return None
    try:
        return (Path(settings.UPLOAD_DIR) / url[len(prefix) :]).read_bytes()
    except OSError:
        return None


async def _dispatch_print_for_bill(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    bill: Bill,
    section: SeatingSection,
    table: Table | None,
    plan_features: dict,
    lines: list[BillLine],
    waiter: Waiter | None = None,
) -> tuple[bool, PrintJobPayload | None, str | None]:
    """Bill printing is available on every plan tier (CLAUDE.md §6, unlike Phase 08's
    KOT printing which is Pro/Pro Max only) — gating here is purely "is a bill printer
    registered for this location", the same shape as `kot_service.send_kot`'s printer
    lookup. The UPI QR embed is the one thing still plan-gated (`qr_upi` feature).
    """
    printer = (
        await session.execute(
            select(Printer).where(
                Printer.tenant_id == tenant_id,
                Printer.location_id == location_id,
                Printer.target == "bill",
                Printer.is_active.is_(True),
            )
        )
    ).scalars().first()
    if printer is None:
        return False, None, None

    hotel = (
        await session.execute(select(HotelMaster).where(HotelMaster.location_id == location_id))
    ).scalar_one_or_none()
    location = (
        await session.execute(select(TenantLocation).where(TenantLocation.id == location_id))
    ).scalar_one()

    hotel_name = hotel.name if hotel else location.name
    # Door No./Street/City/Pincode on one line, phone on its own line below — both
    # centered by the thermal adapter (escpos_thermal.py); the printer fixes batch
    # dropped district (redundant with city for a single-location context) and added
    # phone as a separate, more prominent line.
    address_parts = (
        [p for p in [hotel.door_no, hotel.street, hotel.city, hotel.pincode] if p] if hotel else []
    )
    address_lines = [", ".join(address_parts)] if address_parts else []
    if hotel and hotel.phone:
        address_lines.append(f"Ph: {hotel.phone}")

    payments = (await session.execute(select(Payment).where(Payment.bill_id == bill.id))).scalars().all()

    # "Scan to pay via UPI" only makes sense when the customer actually paid (part of
    # their bill) via UPI — printing it on a cash/card-only bill was showing a payment
    # prompt for money that was already settled a different way.
    qr_payload = None
    if plan_features.get("qr_upi") and hotel and hotel.upi_id and any(p.method == "upi" for p in payments):
        qr_payload = (
            f"upi://pay?pa={quote(hotel.upi_id)}&pn={quote(hotel_name)}"
            f"&am={float(bill.grand_total):.2f}&cu=INR&tn={quote('Bill ' + bill.bill_number)}"
        )

    render_data = BillRenderData(
        bill_number=bill.bill_number,
        table_number=table.table_number if table else None,
        section_name_en=section.name_en,
        created_at=bill.created_at,
        lines=lines,
        subtotal=float(bill.subtotal),
        discount_amount=float(bill.discount_amount),
        discount_note=bill.discount_note,
        cgst_amount=float(bill.cgst_amount),
        sgst_amount=float(bill.sgst_amount),
        round_off_amount=float(bill.round_off_amount),
        grand_total=float(bill.grand_total),
        payments=[(p.method, float(p.amount)) for p in payments],
        hotel_name=hotel_name,
        hotel_address_lines=address_lines,
        gstin=hotel.gstin if hotel else None,
        upi_id=hotel.upi_id if hotel else None,
        qr_payload=qr_payload,
        show_tamil_names=hotel.show_tamil_names if hotel else True,
        party_label=bill.party_label,
        waiter_name=waiter.name if waiter else None,
        paper_width_mm=printer.paper_width_mm,
        logo_image_bytes=_read_uploaded_file(hotel.logo_url) if hotel else None,
        footer_message=(hotel.receipt_footer_message if hotel else None) or _DEFAULT_RECEIPT_FOOTER_MESSAGE,
    )
    content = dispatch_bill_print(printer, render_data)
    # "usb", "local_agent" and "bluetooth" printers are physically attached to (or
    # paired with) the counter machine, not this backend container — hand the rendered
    # bytes back to the frontend so it can push them via WebUSB/local-agent/Web
    # Bluetooth (CLAUDE.md §10) instead of the backend trying (and failing) to reach
    # hardware on someone else's LAN/USB bus/radio. "network"/"wifi" printers, by
    # contrast, are reachable from here directly over the LAN, so the backend sends the
    # raw bytes itself via a plain TCP socket (port 9100 "raw"/JetDirect convention)
    # rather than round-tripping through the browser.
    print_job: PrintJobPayload | None = None
    print_error: str | None = None
    if printer.connection_type in ("usb", "local_agent", "bluetooth"):
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
        printed = False
        print_error = f"{printer.connection_type.replace('_', ' ').title()} printing isn't supported yet."
    return printed, print_job, print_error


async def finalize_bill(
    session: AsyncSession, tenant_id: uuid.UUID, current_user: CurrentUser, req: BillCreateRequest
) -> BillResponse:
    order = await get_order_or_404(session, tenant_id, req.order_id)
    if order.status == "billed":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This order has already been billed")

    plan = await get_active_plan(session, tenant_id)
    plan_features = plan.features if plan else {}
    priced_items = await _load_priced_items(session, order)
    overrides = {uuid.UUID(k): v for k, v in (req.line_tax_overrides or {}).items()}
    totals, discount_note = await _compute_totals(
        session, tenant_id, plan_features, priced_items, req.coupon_code, overrides
    )

    payments_total = round(sum(p.amount for p in req.payments), 2)
    if abs(payments_total - totals.grand_total) > _PAYMENT_AMOUNT_TOLERANCE:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Payments total {payments_total} does not match grand total {totals.grand_total}",
        )

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

    waiter_incentive = _incentive_amount(waiter.incentive_rate if waiter else None, totals.net_taxable_value)
    cashier_incentive = _incentive_amount(pos_user.incentive_rate, totals.net_taxable_value)

    bill = Bill(
        tenant_id=tenant_id,
        location_id=order.location_id,
        order_id=order.id,
        bill_number=await _next_bill_number(session, tenant_id),
        table_id=order.table_id,
        section_id=order.section_id,
        waiter_id=order.waiter_id,
        party_label=order.party_label,
        pos_user_id=order.pos_user_id,
        subtotal=totals.subtotal,
        discount_amount=totals.discount_amount,
        discount_note=discount_note,
        cgst_amount=totals.cgst_amount,
        sgst_amount=totals.sgst_amount,
        round_off_amount=totals.round_off_amount,
        grand_total=totals.grand_total,
        waiter_incentive_amount=waiter_incentive,
        cashier_incentive_amount=cashier_incentive,
        status="finalized",
    )
    session.add(bill)
    await session.flush()

    for priced in totals.priced_items:
        session.add(
            BillItem(
                tenant_id=tenant_id,
                bill_id=bill.id,
                item_id=priced.item.id,
                name_en_snapshot=priced.item.name_en,
                name_ta_snapshot=priced.item.name_ta,
                unit_price=priced.unit_price,
                quantity=priced.quantity,
                line_total=priced.line_total,
            )
        )
    for payment in req.payments:
        session.add(
            Payment(tenant_id=tenant_id, bill_id=bill.id, method=payment.method, amount=payment.amount)
        )

    await _deduct_stock_for_unsent_items(
        session, tenant_id, plan_features, order, bill.id, totals.priced_items
    )

    # "billed" is set here and only here — every other order-mutating path
    # (schemas/orders.py's EDITABLE_ORDER_STATUSES) explicitly excludes it.
    order.status = "billed"

    if totals.discount_amount > _AUDIT_DISCOUNT_THRESHOLD:
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                user_id=current_user.id,
                action="discount_applied",
                entity_type="bill",
                entity_id=bill.id,
                details={
                    "discount_amount": totals.discount_amount,
                    "subtotal": totals.subtotal,
                    "note": discount_note,
                },
            )
        )

    await session.flush()

    lines = [
        BillLine(p.item.name_en, p.item.name_ta, p.quantity, p.unit_price, p.line_total)
        for p in totals.priced_items
    ]
    printed, print_job, print_error = (
        await _dispatch_print_for_bill(
            session, tenant_id, order.location_id, bill, section, table, plan_features, lines, waiter
        )
        if not req.skip_print
        else (False, None, None)
    )

    return await build_bill_response(
        session, bill, printed=printed, print_job=print_job, print_error=print_error
    )


async def get_bill_or_404(session: AsyncSession, tenant_id: uuid.UUID, bill_id: uuid.UUID) -> Bill:
    bill = (
        await session.execute(select(Bill).where(Bill.id == bill_id, Bill.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if bill is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bill not found")
    return bill


async def search_bills(session: AsyncSession, tenant_id: uuid.UUID, params: BillSearchParams) -> list[Bill]:
    """Backs the "Old bill search" screen (CLAUDE.md Phase 09 scope) — by bill number,
    date range, table, waiter, seating section, or cashier (Phase 17).
    """
    query = select(Bill).where(Bill.tenant_id == tenant_id)
    if params.bill_number:
        query = query.where(Bill.bill_number.ilike(f"%{params.bill_number}%"))
    if params.date_from:
        query = query.where(Bill.created_at >= params.date_from)
    if params.date_to:
        query = query.where(Bill.created_at < params.date_to + timedelta(days=1))
    if params.table_id:
        query = query.where(Bill.table_id == params.table_id)
    if params.waiter_id:
        query = query.where(Bill.waiter_id == params.waiter_id)
    if params.location_id:
        query = query.where(Bill.location_id == params.location_id)
    if params.section_id:
        query = query.where(Bill.section_id == params.section_id)
    if params.pos_user_id:
        query = query.where(Bill.pos_user_id == params.pos_user_id)
    rows = await session.execute(query.order_by(Bill.created_at.desc()))
    return list(rows.scalars().all())


async def build_bill_response(
    session: AsyncSession,
    bill: Bill,
    printed: bool = False,
    print_job: PrintJobPayload | None = None,
    print_error: str | None = None,
) -> BillResponse:
    """Renders a persisted bill from its own stored/snapshotted fields — never
    recomputes tax/discount, so a reprint is guaranteed identical to the original
    (CLAUDE.md Phase 09 acceptance criteria).
    """
    section = (
        await session.execute(select(SeatingSection).where(SeatingSection.id == bill.section_id))
    ).scalar_one()
    table = (
        (await session.execute(select(Table).where(Table.id == bill.table_id))).scalar_one()
        if bill.table_id
        else None
    )
    waiter = (
        (await session.execute(select(Waiter).where(Waiter.id == bill.waiter_id))).scalar_one()
        if bill.waiter_id
        else None
    )
    pos_user = (await session.execute(select(User).where(User.id == bill.pos_user_id))).scalar_one()
    bill_items = (await session.execute(select(BillItem).where(BillItem.bill_id == bill.id))).scalars().all()
    payments = (await session.execute(select(Payment).where(Payment.bill_id == bill.id))).scalars().all()

    return BillResponse(
        id=bill.id,
        bill_number=bill.bill_number,
        order_id=bill.order_id,
        location_id=bill.location_id,
        table_id=bill.table_id,
        table_number=table.table_number if table else None,
        section_id=bill.section_id,
        section_name_en=section.name_en,
        waiter_id=bill.waiter_id,
        waiter_name=waiter.name if waiter else None,
        party_label=bill.party_label,
        pos_user_id=bill.pos_user_id,
        pos_user_login_id=pos_user.user_id,
        status=bill.status,
        items=[
            BillItemResponse(
                id=bi.id,
                item_id=bi.item_id,
                name_en=bi.name_en_snapshot,
                name_ta=bi.name_ta_snapshot,
                unit_price=float(bi.unit_price),
                quantity=bi.quantity,
                line_total=float(bi.line_total),
            )
            for bi in bill_items
        ],
        subtotal=float(bill.subtotal),
        discount_amount=float(bill.discount_amount),
        discount_note=bill.discount_note,
        cgst_amount=float(bill.cgst_amount),
        sgst_amount=float(bill.sgst_amount),
        round_off_amount=float(bill.round_off_amount),
        grand_total=float(bill.grand_total),
        waiter_incentive_amount=(
            float(bill.waiter_incentive_amount) if bill.waiter_incentive_amount is not None else None
        ),
        cashier_incentive_amount=(
            float(bill.cashier_incentive_amount) if bill.cashier_incentive_amount is not None else None
        ),
        payments=[PaymentResponse(method=p.method, amount=float(p.amount)) for p in payments],
        printed=printed,
        print_job=print_job,
        print_error=print_error,
        created_at=bill.created_at,
    )


async def reprint_bill(
    session: AsyncSession, tenant_id: uuid.UUID, bill: Bill
) -> tuple[bool, PrintJobPayload | None, str | None]:
    section = (
        await session.execute(select(SeatingSection).where(SeatingSection.id == bill.section_id))
    ).scalar_one()
    table = (
        (await session.execute(select(Table).where(Table.id == bill.table_id))).scalar_one()
        if bill.table_id
        else None
    )
    bill_items = (
        (await session.execute(select(BillItem).where(BillItem.bill_id == bill.id))).scalars().all()
    )
    lines = [
        BillLine(
            bi.name_en_snapshot, bi.name_ta_snapshot, bi.quantity, float(bi.unit_price), float(bi.line_total)
        )
        for bi in bill_items
    ]
    waiter = (
        (await session.execute(select(Waiter).where(Waiter.id == bill.waiter_id))).scalar_one_or_none()
        if bill.waiter_id
        else None
    )
    plan = await get_active_plan(session, tenant_id)
    plan_features = plan.features if plan else {}
    return await _dispatch_print_for_bill(
        session, tenant_id, bill.location_id, bill, section, table, plan_features, lines, waiter
    )
