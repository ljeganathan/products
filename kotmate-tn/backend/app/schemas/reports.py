import uuid
from datetime import date

from pydantic import BaseModel


class ReportQueryParams(BaseModel):
    """Shared filter shape for every report endpoint — date range (inclusive on both
    ends; the service applies an exclusive `date_to + 1 day` bound against
    `Bill.created_at`, mirroring `bill_service.search_bills`) plus an optional
    single-location filter. Every report is tenant-scoped on top of this via RLS.
    """

    date_from: date
    date_to: date
    location_id: uuid.UUID | None = None


class PaymentMethodTotal(BaseModel):
    method: str
    amount: float


class SalesSummaryResponse(BaseModel):
    bill_count: int
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    average_bill_value: float
    # Per-payment-method breakdown, same shape as ZReportResponse.payments below — added
    # so Sales Summary's print/export can show "Payment - Cash/UPI/Card" like the Z-Report
    # already does (production feedback round 3).
    payments: list[PaymentMethodTotal]


class ItemWiseSalesRow(BaseModel):
    item_id: uuid.UUID
    name_en: str
    name_ta: str | None
    # Item's current (live) category — categories aren't versioned anywhere in this
    # schema, same "live reference data" treatment CategoryWiseSalesRow already has, see
    # report_service.item_wise_sales. Used to group this report by category (production
    # feedback round 4).
    category_id: uuid.UUID
    category_name_en: str
    category_name_ta: str | None
    quantity_sold: int
    revenue: float


class ItemWiseSalesResponse(BaseModel):
    # Pre-grouped: categories ordered by their own total revenue descending, items within
    # each category ordered by their own revenue descending (production feedback round 4)
    # — not a flat revenue-desc list across all items like before.
    rows: list[ItemWiseSalesRow]
    total_revenue: float


class CategoryWiseSalesRow(BaseModel):
    category_id: uuid.UUID
    name_en: str
    name_ta: str | None
    quantity_sold: int
    revenue: float


class CategoryWiseSalesResponse(BaseModel):
    rows: list[CategoryWiseSalesRow]
    total_revenue: float


class TaxSummaryResponse(BaseModel):
    taxable_value: float
    cgst_amount: float
    sgst_amount: float
    total_tax: float


class WaiterSalesRow(BaseModel):
    waiter_id: uuid.UUID
    waiter_name: str
    bill_count: int
    net_sale_value: float


class WaiterSalesResponse(BaseModel):
    rows: list[WaiterSalesRow]
    total_net_sale_value: float


class CashierSalesRow(BaseModel):
    pos_user_id: uuid.UUID
    login_id: str
    name: str
    bill_count: int
    net_sale_value: float


class CashierSalesResponse(BaseModel):
    rows: list[CashierSalesRow]
    total_net_sale_value: float


class WaiterIncentiveRow(BaseModel):
    """Reconciles exactly against the live incentive line on each bill's POS summary —
    `incentive_amount` here is a straight SUM of `bills.waiter_incentive_amount`, which
    was itself computed and stored once at bill-finalize time (Phase 09), never
    recomputed here (CLAUDE.md §11).
    """

    waiter_id: uuid.UUID
    waiter_name: str
    net_sale_value: float
    incentive_amount: float


class WaiterIncentiveResponse(BaseModel):
    rows: list[WaiterIncentiveRow]
    total_incentive_amount: float


class CashierIncentiveRow(BaseModel):
    pos_user_id: uuid.UUID
    login_id: str
    name: str
    net_sale_value: float
    incentive_amount: float


class CashierIncentiveResponse(BaseModel):
    rows: list[CashierIncentiveRow]
    total_incentive_amount: float


class PosOperatorSalesRow(BaseModel):
    pos_user_id: uuid.UUID
    login_id: str
    name: str
    bill_count: int
    net_sale_value: float


class PosOperatorSalesResponse(BaseModel):
    rows: list[PosOperatorSalesRow]
    total_net_sale_value: float


class PosOperatorIncentiveRow(BaseModel):
    pos_user_id: uuid.UUID
    login_id: str
    name: str
    net_sale_value: float
    incentive_amount: float


class PosOperatorIncentiveResponse(BaseModel):
    rows: list[PosOperatorIncentiveRow]
    total_incentive_amount: float


class OrderTypeSalesRow(BaseModel):
    """One row per `seating_sections` row (AC/Non-AC/Rooftop/Takeaway/Online Delivery/
    ...) — not collapsed into a single "Dine In" bucket, so a tenant can see e.g. AC vs
    Rooftop sales separately, not just dine-in vs parcel vs online as one lump figure.
    """

    section_id: uuid.UUID
    label: str
    bill_count: int
    net_sale_value: float


class OrderTypeSalesResponse(BaseModel):
    rows: list[OrderTypeSalesRow]
    total_bill_count: int
    total_net_sale_value: float


class ItemListPriceOverride(BaseModel):
    """One per-section override on an item (`item_section_prices`, CLAUDE.md §11
    Seating-section-aware pricing, Pro+) — absence of a row for a section means that
    section falls back to the item's own base price, so only real overrides appear here.
    """

    section_id: uuid.UUID
    section_name_en: str
    price: float


class ItemListRow(BaseModel):
    item_id: uuid.UUID
    item_code: str | None
    name_en: str
    name_ta: str | None
    category_id: uuid.UUID
    category_name_en: str
    category_name_ta: str | None
    base_price: float
    price_overrides: list[ItemListPriceOverride]


class ItemListResponse(BaseModel):
    """Unlike every other report here, this isn't a sales figure for a date range — it's
    a snapshot of the current item catalog (CLAUDE.md §8 `items`), grouped by category.
    """

    rows: list[ItemListRow]
    total_items: int


class ZReportResponse(BaseModel):
    """Daily shift-close summary for a single business day (CLAUDE.md §11)."""

    report_date: date
    bill_count: int
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    payments: list[PaymentMethodTotal]


class DiscountSummaryRow(BaseModel):
    """One row per discount rule name that fired at least once in the date range
    (Phase 27) — sourced from `bill_discounts`, not from parsing `bills.discount_note`.
    `bills.grand_total` is already net of discount (post-discount, post-tax) and is what
    Sales Summary reports as sales, so `sales_after_discount` is exactly that figure and
    `total_bill_amount` is the bill before discount (`sales + discount`) — Total Bill −
    Discount = Sales on every row. A bill touched by more than one rule is counted under
    every rule it touched (its own sales figure repeated), so the TOTAL row of a
    multi-rule period can exceed Sales Summary's grand total.
    """

    discount_name: str
    total_bill_amount: float
    discount_amount: float
    sales_after_discount: float


class DiscountSummaryResponse(BaseModel):
    rows: list[DiscountSummaryRow]
    total_bill_amount: float
    total_discount_amount: float
    total_sales_after_discount: float


class DiscountDetailRow(BaseModel):
    """Same grouping/basis as `DiscountSummaryRow`, broken out to one row per
    (discount rule, bill) pair instead of aggregated — `customer_name`/`customer_phone`
    are the bill's own snapshotted fields (Phase 27), null on a bill nobody entered them
    for.
    """

    discount_name: str
    bill_number: str
    customer_name: str | None
    customer_phone: str | None
    total_bill_amount: float
    discount_amount: float
    sales_after_discount: float


class DiscountDetailResponse(BaseModel):
    # Pre-sorted rule-major (discount name, then bill date) — same "caller never
    # re-sorts" contract item_wise_sales already guarantees for its category grouping.
    rows: list[DiscountDetailRow]
    total_bill_amount: float
    total_discount_amount: float
    total_sales_after_discount: float
