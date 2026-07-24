import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill, BillItem
from app.models.enums import BillStatus, DiscountType, StockMovementReason
from app.repositories.bill_repository import BillRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.tax_profile_repository import TaxProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.bill import (
    BillCreate,
    BillItemCreate,
    BillPrintPayload,
    PrintPayloadItem,
    ResumeBillResponse,
)
from app.schemas.company_settings import CompanySettingsOut
from app.services.company_settings_service import get_or_create_company_settings
from app.services.stock_service import adjust_stock


@dataclass
class LineInput:
    item_id: uuid.UUID
    name: str
    unit_price_paise: int
    qty: float
    cgst_pct: float
    sgst_pct: float
    igst_pct: float
    discount_type: DiscountType | None
    discount_value: int | None


@dataclass
class LineResult:
    item_id: uuid.UUID
    name: str
    qty: float
    unit_price_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    line_total_paise: int
    tax_profile_snapshot: dict


@dataclass
class BillTotals:
    lines: list[LineResult]
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    round_off_paise: int
    total_paise: int


def _line_discount_paise(
    gross_paise: int, discount_type: DiscountType | None, discount_value: int | None
) -> int:
    if not discount_type or not discount_value:
        return 0
    if discount_type == DiscountType.FLAT:
        return min(discount_value, gross_paise)
    # PERCENT: discount_value is basis points (10.50% -> 1050), per discount_rules.value.
    return min(round(gross_paise * discount_value / 10_000), gross_paise)


def compute_bill_totals(
    lines: list[LineInput],
    bill_discount_type: DiscountType | None,
    bill_discount_value: int | None,
) -> BillTotals:
    """Server-authoritative totals engine — the only place bill money math
    happens. Tax is computed per line (each item keeps its own GST slab, so
    a mixed-rate cart is correct), and a bill-level discount is prorated
    across lines by their share of the post-item-discount subtotal *before*
    that line's tax is applied — required for GST correctness when items in
    the same bill have different slabs. Never trust client-sent totals;
    this is what actually gets persisted and printed.

    Billing here always applies cgst_pct + sgst_pct (intra-state), per
    CLAUDE.md §8's Phase 5 scope. A tax_profile's igst_pct is stored
    alongside cgst/sgst on the *same* profile as the equivalent inter-state
    rate for future invoicing (docs/DATABASE_SCHEMA.md) — it doesn't mark
    a profile as inter-state-only, so it's simply not read here."""
    gross_per_line = [round(line.unit_price_paise * line.qty) for line in lines]
    subtotal_paise = sum(gross_per_line)

    item_discount_per_line = [
        _line_discount_paise(gross, line.discount_type, line.discount_value)
        for line, gross in zip(lines, gross_per_line, strict=True)
    ]
    net_after_item_discount = [
        g - d for g, d in zip(gross_per_line, item_discount_per_line, strict=True)
    ]
    net_before_bill_discount = sum(net_after_item_discount)

    if bill_discount_type and bill_discount_value and net_before_bill_discount > 0:
        if bill_discount_type == DiscountType.FLAT:
            bill_discount_paise = min(bill_discount_value, net_before_bill_discount)
        else:
            bill_discount_paise = min(
                round(net_before_bill_discount * bill_discount_value / 10_000),
                net_before_bill_discount,
            )
    else:
        bill_discount_paise = 0

    line_results: list[LineResult] = []
    total_cgst = 0
    total_sgst = 0
    allocated_bill_discount = 0
    last_index = len(lines) - 1

    for i, (line, item_disc, net) in enumerate(
        zip(lines, item_discount_per_line, net_after_item_discount, strict=True)
    ):
        if net_before_bill_discount > 0 and bill_discount_paise > 0:
            if i == last_index:
                # Last line absorbs the rounding remainder so the prorated
                # shares always sum exactly to bill_discount_paise.
                line_bill_discount_share = bill_discount_paise - allocated_bill_discount
            else:
                line_bill_discount_share = round(
                    bill_discount_paise * net / net_before_bill_discount
                )
        else:
            line_bill_discount_share = 0
        allocated_bill_discount += line_bill_discount_share

        taxable = max(net - line_bill_discount_share, 0)
        cgst = round(taxable * line.cgst_pct / 100)
        sgst = round(taxable * line.sgst_pct / 100)
        total_cgst += cgst
        total_sgst += sgst

        line_results.append(
            LineResult(
                item_id=line.item_id,
                name=line.name,
                qty=line.qty,
                unit_price_paise=line.unit_price_paise,
                discount_paise=item_disc + line_bill_discount_share,
                cgst_paise=cgst,
                sgst_paise=sgst,
                line_total_paise=taxable + cgst + sgst,
                tax_profile_snapshot={
                    "cgst_pct": line.cgst_pct,
                    "sgst_pct": line.sgst_pct,
                    "igst_pct": line.igst_pct,
                },
            )
        )

    total_discount_paise = sum(item_discount_per_line) + bill_discount_paise
    raw_total = subtotal_paise - total_discount_paise + total_cgst + total_sgst
    # Round to the nearest rupee, as is standard for Indian retail billing;
    # the difference is shown to the customer as its own round-off line.
    rounded_total = round(raw_total / 100) * 100
    round_off_paise = rounded_total - raw_total

    return BillTotals(
        lines=line_results,
        subtotal_paise=subtotal_paise,
        discount_paise=total_discount_paise,
        cgst_paise=total_cgst,
        sgst_paise=total_sgst,
        round_off_paise=round_off_paise,
        total_paise=rounded_total,
    )


async def create_bill(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    store_id: uuid.UUID,
    cashier_id: uuid.UUID,
    payload: BillCreate,
) -> tuple[Bill, list[BillItem]]:
    item_repo = ItemRepository(db)
    tax_repo = TaxProfileRepository(db)
    bill_repo = BillRepository(db)

    line_inputs: list[LineInput] = []
    for line in payload.items:
        item = await item_repo.get_by_id_for_tenant(line.item_id, tenant_id)
        if item is None or not item.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item {line.item_id} not found or inactive",
            )
        tax_profile = await tax_repo.get_by_id_for_tenant(item.tax_profile_id, tenant_id)
        if tax_profile is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Item '{item.name_en}' has no valid tax profile",
            )
        line_inputs.append(
            LineInput(
                item_id=item.id,
                name=item.name_en,
                unit_price_paise=item.selling_price_paise,
                qty=line.qty,
                cgst_pct=float(tax_profile.cgst_pct),
                sgst_pct=float(tax_profile.sgst_pct),
                igst_pct=float(tax_profile.igst_pct),
                discount_type=line.discount_type,
                discount_value=line.discount_value,
            )
        )

    try:
        totals = compute_bill_totals(
            line_inputs, payload.bill_discount_type, payload.bill_discount_value
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    bill_number = await bill_repo.next_bill_number(tenant_id, store_id)
    bill = Bill(
        tenant_id=tenant_id,
        store_id=store_id,
        bill_number=bill_number,
        cashier_id=cashier_id,
        customer_name=payload.customer_name,
        customer_phone=payload.customer_phone,
        subtotal_paise=totals.subtotal_paise,
        discount_paise=totals.discount_paise,
        cgst_paise=totals.cgst_paise,
        sgst_paise=totals.sgst_paise,
        round_off_paise=totals.round_off_paise,
        total_paise=totals.total_paise,
        payment_mode=payload.payment_mode,
        status=BillStatus.HELD if payload.hold else BillStatus.COMPLETED,
    )
    try:
        await bill_repo.create(bill)
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Could not allocate a bill number — please retry",
        ) from exc

    bill_items = [
        BillItem(
            bill_id=bill.id,
            item_id=lr.item_id,
            item_name_snapshot=lr.name,
            qty=lr.qty,
            unit_price_paise=lr.unit_price_paise,
            discount_paise=lr.discount_paise,
            tax_profile_snapshot_json=lr.tax_profile_snapshot,
            line_total_paise=lr.line_total_paise,
        )
        for lr in totals.lines
    ]
    await bill_repo.add_items(bill_items)

    if not payload.hold:
        for line_input in line_inputs:
            await adjust_stock(
                db,
                tenant_id=tenant_id,
                store_id=store_id,
                item_id=line_input.item_id,
                change_qty=-line_input.qty,
                reason=StockMovementReason.SALE,
                reference_id=bill.id,
                created_by=cashier_id,
            )

    return bill, bill_items


async def cancel_bill(db: AsyncSession, *, bill: Bill, cashier_id: uuid.UUID) -> None:
    if bill.status == BillStatus.CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bill is already cancelled"
        )

    if bill.status == BillStatus.COMPLETED:
        bill_repo = BillRepository(db)
        for item in await bill_repo.get_items(bill.id):
            await adjust_stock(
                db,
                tenant_id=bill.tenant_id,
                store_id=bill.store_id,
                item_id=item.item_id,
                change_qty=float(item.qty),
                reason=StockMovementReason.RETURN,
                reference_id=bill.id,
                created_by=cashier_id,
            )

    bill.status = BillStatus.CANCELLED
    await db.flush()


async def resume_held_bill(db: AsyncSession, *, bill: Bill) -> ResumeBillResponse:
    """Pops a held bill back into an editable cart: returns its contents and
    deletes the held row, since the cashier will POST /bills again to
    actually finalize (a fresh bill number is assigned then). Per-line/bill
    discounts are not restored — only item_id/qty/customer/payment_mode are
    reconstructible from what `bill_items` stores; the cashier re-applies
    discounts if still wanted. Documented in API_CONTRACTS.md."""
    bill_repo = BillRepository(db)
    items = await bill_repo.get_items(bill.id)
    response = ResumeBillResponse(
        store_id=bill.store_id,
        customer_name=bill.customer_name,
        customer_phone=bill.customer_phone,
        payment_mode=bill.payment_mode,
        items=[
            BillItemCreate(
                item_id=i.item_id, qty=float(i.qty), discount_type=None, discount_value=None
            )
            for i in items
        ],
    )
    await bill_repo.delete_with_items(bill)
    return response


async def build_print_payload(
    db: AsyncSession, *, bill: Bill, items: list[BillItem]
) -> BillPrintPayload:
    company = await get_or_create_company_settings(
        db, tenant_id=bill.tenant_id, store_id=bill.store_id
    )
    cashier = await UserRepository(db).get_by_id(bill.cashier_id)

    return BillPrintPayload(
        bill_number=bill.bill_number,
        created_at=bill.created_at,
        cashier_name=cashier.name if cashier else "Unknown",
        customer_name=bill.customer_name,
        customer_phone=bill.customer_phone,
        company=CompanySettingsOut.model_validate(company),
        items=[
            PrintPayloadItem(
                name=i.item_name_snapshot,
                qty=float(i.qty),
                unit_price_paise=i.unit_price_paise,
                discount_paise=i.discount_paise,
                line_total_paise=i.line_total_paise,
            )
            for i in items
        ],
        subtotal_paise=bill.subtotal_paise,
        discount_paise=bill.discount_paise,
        cgst_paise=bill.cgst_paise,
        sgst_paise=bill.sgst_paise,
        round_off_paise=bill.round_off_paise,
        total_paise=bill.total_paise,
        payment_mode=bill.payment_mode,
    )
