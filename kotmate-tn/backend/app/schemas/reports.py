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


class SalesSummaryResponse(BaseModel):
    bill_count: int
    subtotal: float
    discount_amount: float
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    average_bill_value: float


class ItemWiseSalesRow(BaseModel):
    item_id: uuid.UUID
    name_en: str
    name_ta: str | None
    quantity_sold: int
    revenue: float


class ItemWiseSalesResponse(BaseModel):
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


class PaymentMethodTotal(BaseModel):
    method: str
    amount: float


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
