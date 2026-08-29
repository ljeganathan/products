import uuid
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Printer, Role, Tenant, User
from app.printing.base import _PAYMENT_LABELS, ReportBody, ReportRenderData, format_inr, now_ist
from app.printing.dispatcher import dispatch_report_print
from app.schemas.report_print import ReportPrintRequest
from app.schemas.reports import (
    CashierIncentiveResponse,
    CashierSalesResponse,
    CategoryWiseSalesResponse,
    CategoryWiseSalesRow,
    ItemListRow,
    ItemWiseSalesResponse,
    ItemWiseSalesRow,
    OrderTypeSalesResponse,
    PaymentMethodTotal,
    PosOperatorIncentiveResponse,
    PosOperatorSalesResponse,
    ReportQueryParams,
    SalesSummaryResponse,
    TaxSummaryResponse,
    WaiterIncentiveResponse,
    WaiterSalesResponse,
    ZReportResponse,
)
from app.services import report_service
from app.services.branch_header import resolve_branch_header

# Reports (and so Z-Report's "Closed By" line) are only ever printed by a tenant_admin
# or pos_user/Cashier — reports.py's router requires one of those two roles — so this
# only needs to cover the two labels a shift-closer can actually have.
_CLOSER_ROLE_LABELS = {"tenant_admin": "Admin", "pos_user": "Cashier"}

# Public (not `_`-prefixed) — reports.py's export endpoints reuse this same title-per-
# report_type map so an exported file's title/filename always matches what the print
# path already uses (production feedback round 4: one column/title format everywhere).
REPORT_TITLES = {
    "sales-summary": "Sales Summary",
    "item-wise": "Item Wise Sales",
    "category-wise": "Category Wise Sales",
    "tax-summary": "Tax Summary",
    "waiter-wise": "Waiter Wise Sales",
    "cashier-wise": "Cashier Wise Sales",
    "waiter-incentive": "Waiter Incentive",
    "cashier-incentive": "Cashier Incentive",
    "pos-operator-wise": "POS Operator Wise Sales",
    "pos-operator-incentive": "POS Operator Incentive",
    "z-report": "Z Report",
    "item-list": "Item List",
    "order-type-wise": "Order Type Wise Sales",
}

# Order the user asked for — Cash, then UPI, then Card — not the UPI-first order the
# live POS payment buttons use (CLAUDE.md §9); a printed summary reads top-to-bottom
# once, so this just follows the literal production-feedback spec.
_SUMMARY_PAYMENT_METHODS = ("cash", "upi", "card")


def has_report_printing_feature(plan_features: dict | None) -> bool:
    """Plan-tier gate (Pro Max only) — seeded via the printer_reports_target migration
    (f4a01d6c3b87), which set `features.report_printing = true` on the pro_max plan row
    only. Unlike stock_management, there is no "always on for tiers without it" fallback
    here — Lite/Pro never see report printing at all.
    """
    return bool((plan_features or {}).get("report_printing"))


def is_report_printing_enabled(tenant: Tenant, plan_features: dict | None) -> bool:
    """Effective on/off state — the single flag every consumer (ReportsPage's Print
    button, the print endpoint itself) should check. Requires both the plan feature AND
    the tenant's own toggle (Settings > Preferences), which defaults off.
    """
    if not has_report_printing_feature(plan_features):
        return False
    return bool(tenant.report_printing_enabled)


def _amount(value: float) -> str:
    """Every printed amount, report-wide (production feedback round 3): no "Rs."
    prefix — a report is read as a self-contained financial statement, not a
    customer-facing bill, so the currency symbol is redundant column-wide — and always
    two decimal places (unlike the bill/KOT "paise only when non-zero" convention) so a
    column of amounts lines up consistently, right-justified, the way a real financial
    statement's numbers do.
    """
    return format_inr(value, symbol="", always_paise=True)


def _payment_pairs(payments: list[PaymentMethodTotal]) -> list[tuple[str, str]]:
    by_method = {p.method: p.amount for p in payments}
    return [
        (f"Payment - {_PAYMENT_LABELS.get(method, method)}", _amount(by_method.get(method, 0.0)))
        for method in _SUMMARY_PAYMENT_METHODS
    ]


def _summary_pairs(
    bill_count: int,
    subtotal: float,
    discount_amount: float,
    cgst_amount: float,
    sgst_amount: float,
    round_off_amount: float,
    grand_total: float,
    payments: list[PaymentMethodTotal],
) -> list[tuple[str, str]]:
    """Shared row-wise field list for Sales Summary and Z-Report — both reduce to the
    same 10 lines (production feedback round 3: "row wise not column wise").
    """
    return [
        ("Total Bill Count", str(bill_count)),
        ("Subtotal", _amount(subtotal)),
        ("Discount", _amount(discount_amount)),
        ("CGST", _amount(cgst_amount)),
        ("SGST", _amount(sgst_amount)),
        ("Round Off", _amount(round_off_amount)),
        ("Grand Total", _amount(grand_total)),
        *_payment_pairs(payments),
    ]


def _category_wise_body(
    rows_data: list[CategoryWiseSalesRow], tamil_names_enabled: bool, total_revenue: float
) -> ReportBody:
    """Category Wise Sales — one Name column (was two: name_en + name_ta), "Qty"/"Sales"
    headers, no "Rs." on amounts, and a bold+double-height TOTAL row (production feedback
    round 3).

    `rows[i][0]` is always the English name — needed as-is by the dot-matrix adapter
    (which has no image support and so always falls back to English, CLAUDE.md §10), by
    the CSV/Excel/PDF export (report_body_to_grid, production feedback round 4 — a text
    format has no reason to ever drop the name), and as the base row the thermal adapter
    blanks when it prints a rasterized Tamil line instead (see ReportBody's own docstring,
    printing/base.py). Only `tamil_names` (built here from `tamil_names_enabled`) tells
    the thermal adapter which rows should show Tamil at all.
    """
    headers = ["Name", "Qty", "Sales"]
    rows: list[list[str]] = []
    tamil_names: dict[int, str] = {}
    for idx, r in enumerate(rows_data):
        rows.append([r.name_en, str(r.quantity_sold), _amount(r.revenue)])
        if tamil_names_enabled and r.name_ta:
            tamil_names[idx] = r.name_ta
    total_idx = len(rows)
    rows.append(["TOTAL", "", _amount(total_revenue)])
    return ReportBody(
        kind="grid",
        headers=headers,
        rows=rows,
        bold_rows={total_idx},
        big_rows={total_idx},
        tamil_names=tamil_names,
    )


def _item_wise_body(
    rows_data: list[ItemWiseSalesRow], tamil_names_enabled: bool, total_revenue: float
) -> ReportBody:
    """Item Wise Sales — same Name/Qty/Sales shape as `_category_wise_body`, but grouped
    by category: each category gets its own bold group-header row (name only, Qty/Sales
    left blank) ahead of its items (production feedback round 4 — applies to print and,
    via `report_body_to_grid`, to CSV/Excel/PDF export too). `report_service.item_wise_sales`
    already returns `rows_data` pre-ordered category-major (categories by total revenue
    descending, items within a category by their own revenue descending), so this only
    has to notice where one category's run of rows ends and the next begins — it never
    re-sorts anything itself.
    """
    headers = ["Name", "Qty", "Sales"]
    rows: list[list[str]] = []
    bold_rows: set[int] = set()
    tamil_names: dict[int, str] = {}
    current_category_id = None
    for r in rows_data:
        if r.category_id != current_category_id:
            current_category_id = r.category_id
            header_idx = len(rows)
            rows.append([r.category_name_en, "", ""])
            bold_rows.add(header_idx)
            if tamil_names_enabled and r.category_name_ta:
                tamil_names[header_idx] = r.category_name_ta
        idx = len(rows)
        rows.append([r.name_en, str(r.quantity_sold), _amount(r.revenue)])
        if tamil_names_enabled and r.name_ta:
            tamil_names[idx] = r.name_ta
    total_idx = len(rows)
    bold_rows.add(total_idx)
    rows.append(["TOTAL", "", _amount(total_revenue)])
    return ReportBody(
        kind="grid",
        headers=headers,
        rows=rows,
        bold_rows=bold_rows,
        big_rows={total_idx},
        tamil_names=tamil_names,
    )


def _sales_grid_body(
    headers: list[str],
    names_and_counts: list[tuple[str, int, float]],
    total_label: str,
    total_net_sale_value: float,
) -> ReportBody:
    """Waiter/Cashier/POS-Operator Wise Sales all reduce to (Name, Bill Count, Sales) —
    `login_id` (Cashier/POS-Operator rows carry one) is deliberately dropped here even
    though it stays in the CSV/Excel/PDF export, matching the round's "print only" scope.
    """
    rows = [
        [name, str(bill_count), _amount(net_sale_value)]
        for name, bill_count, net_sale_value in names_and_counts
    ]
    rows.append([total_label, "", _amount(total_net_sale_value)])
    return ReportBody(kind="grid", headers=headers, rows=rows)


def _order_type_pairs(result: OrderTypeSalesResponse) -> list[tuple[str, str]]:
    """Row-wise, not the grid every other -wise-sales report uses (production feedback:
    a POS printer's paper is too narrow for a 3-column Name/Bill Count/Sales grid once
    section names get long, e.g. "Online Delivery") — same "Field - Bills"/"Field -
    Sales" pair-per-line shape as Z-Report's own payment breakdown (`_payment_pairs`).
    """
    pairs: list[tuple[str, str]] = []
    for r in result.rows:
        pairs.append((f"{r.label} - Bills", str(r.bill_count)))
        pairs.append((f"{r.label} - Sales", _amount(r.net_sale_value)))
    pairs.append(("TOTAL - Bills", str(result.total_bill_count)))
    pairs.append(("TOTAL - Sales", _amount(result.total_net_sale_value)))
    return pairs


def _incentive_grid_body(
    headers: list[str],
    names_and_amounts: list[tuple[str, float, float]],
    total_label: str,
    total_incentive_amount: float,
) -> ReportBody:
    """Waiter/Cashier/POS-Operator Incentive all reduce to (Name, Net Sales, Incentive
    Amt) — same login_id-dropped, no-"Rs." treatment as the sales-grid reports above.
    """
    rows = [
        [name, _amount(net_sale_value), _amount(incentive_amount)]
        for name, net_sale_value, incentive_amount in names_and_amounts
    ]
    rows.append([total_label, "", _amount(total_incentive_amount)])
    return ReportBody(kind="grid", headers=headers, rows=rows)


def item_list_print_body(rows_data: list[ItemListRow]) -> ReportBody:
    """Item List's print copy is a condensed price list — English name and base price
    only, grouped by category with a bold header row per category, same grouping idiom
    as `_item_wise_body` — regardless of the tenant's `report_tamil_names_enabled`
    toggle and of any per-section price override. A physical list taped up at a counter
    has no room for either: staff read the base price off it, not a per-section table.

    This is why item-list is the one report_type whose print body isn't built via the
    shared `build_report_body` below — see `item_list_export_grid` for the CSV/Excel/PDF
    export shape, which deliberately shows both languages and every override instead.
    """
    headers = ["Code", "Name", "Price"]
    rows: list[list[str]] = []
    bold_rows: set[int] = set()
    current_category_id = None
    for r in rows_data:
        if r.category_id != current_category_id:
            current_category_id = r.category_id
            header_idx = len(rows)
            rows.append(["", r.category_name_en, ""])
            bold_rows.add(header_idx)
        rows.append([r.item_code or "", r.name_en, _amount(r.base_price)])
    # Two leading text columns (Code, Name) — ReportBody's left_align_columns defaults
    # to just {0}, which would right-justify Name against the Price column (bug fix:
    # Name was printing flush-right instead of left-aligned once Code pushed it to
    # column 1).
    return ReportBody(kind="grid", headers=headers, rows=rows, bold_rows=bold_rows, left_align_columns={0, 1})


def item_list_export_grid(rows_data: list[ItemListRow]) -> tuple[list[str], list[list[str]]]:
    """CSV/Excel/PDF export (and the on-screen Reports table) show full item-master
    detail unlike the condensed print copy above: both English and Tamil names, and every
    active per-section price override (comma-separated "Section: Price" pairs) alongside
    the base price — this is back-office reference data, not a counter price list.
    """
    headers = ["Item Code", "Name (English)", "Name (Tamil)", "Category", "Base Price", "Price Overrides"]
    grid: list[list[str]] = []
    for r in rows_data:
        overrides = "; ".join(f"{o.section_name_en}: {_amount(o.price)}" for o in r.price_overrides)
        grid.append(
            [
                r.item_code or "",
                r.name_en,
                r.name_ta or "",
                r.category_name_en,
                _amount(r.base_price),
                overrides,
            ]
        )
    return headers, grid


def build_report_body(report_type: str, result: object, tamil_names_enabled: bool = False) -> ReportBody:
    """Builds the printer-shaped `ReportBody` (renamed/no-"Rs." grid columns, row-wise
    key-value summaries) from an already-fetched `report_service` result — the single
    place both the thermal/dot-matrix print path (`render_report_print_bytes` below) and
    the CSV/Excel/PDF export path (reports.py's `_export_response`, via
    `report_body_to_grid`) get their column shape from, so a print and an export of the
    same report can never drift apart (production feedback round 4: "keep the same
    format of the columns... for csv/pdf/excel").

    `tamil_names_enabled` only matters to the print path (it decides which rows the
    thermal adapter additionally rasterizes as Tamil) — export ignores `body.tamil_names`
    entirely and always reads the row's own English text, so export call sites can leave
    it at its default.
    """
    if report_type == "sales-summary":
        result = cast(SalesSummaryResponse, result)
        return ReportBody(kind="keyvalue", pairs=_summary_pairs(
            result.bill_count, result.subtotal, result.discount_amount, result.cgst_amount,
            result.sgst_amount, result.round_off_amount, result.grand_total, result.payments,
        ))
    if report_type == "item-wise":
        result = cast(ItemWiseSalesResponse, result)
        return _item_wise_body(result.rows, tamil_names_enabled, result.total_revenue)
    if report_type == "category-wise":
        result = cast(CategoryWiseSalesResponse, result)
        return _category_wise_body(result.rows, tamil_names_enabled, result.total_revenue)
    if report_type == "order-type-wise":
        result = cast(OrderTypeSalesResponse, result)
        return ReportBody(kind="keyvalue", pairs=_order_type_pairs(result))
    if report_type == "tax-summary":
        result = cast(TaxSummaryResponse, result)
        return ReportBody(
            kind="keyvalue",
            pairs=[
                ("Taxable Value", _amount(result.taxable_value)),
                ("CGST", _amount(result.cgst_amount)),
                ("SGST", _amount(result.sgst_amount)),
                ("Total Tax", _amount(result.total_tax)),
            ],
        )
    if report_type == "waiter-wise":
        result = cast(WaiterSalesResponse, result)
        rows = [(r.waiter_name, r.bill_count, r.net_sale_value) for r in result.rows]
        return _sales_grid_body(
            ["Waiter Name", "Bill Count", "Sales"], rows, "TOTAL", result.total_net_sale_value
        )
    if report_type == "cashier-wise":
        result = cast(CashierSalesResponse, result)
        rows = [(r.name, r.bill_count, r.net_sale_value) for r in result.rows]
        return _sales_grid_body(
            ["Cashier Name", "Bill Count", "Sales"], rows, "TOTAL", result.total_net_sale_value
        )
    if report_type == "pos-operator-wise":
        result = cast(PosOperatorSalesResponse, result)
        rows = [(r.name, r.bill_count, r.net_sale_value) for r in result.rows]
        return _sales_grid_body(
            ["Name", "Bill Count", "Sales"], rows, "TOTAL", result.total_net_sale_value
        )
    if report_type == "waiter-incentive":
        result = cast(WaiterIncentiveResponse, result)
        rows = [(r.waiter_name, r.net_sale_value, r.incentive_amount) for r in result.rows]
        return _incentive_grid_body(
            ["Waiter Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
        )
    if report_type == "cashier-incentive":
        result = cast(CashierIncentiveResponse, result)
        rows = [(r.name, r.net_sale_value, r.incentive_amount) for r in result.rows]
        return _incentive_grid_body(
            ["Cashier Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
        )
    if report_type == "pos-operator-incentive":
        result = cast(PosOperatorIncentiveResponse, result)
        rows = [(r.name, r.net_sale_value, r.incentive_amount) for r in result.rows]
        return _incentive_grid_body(
            ["Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
        )
    if report_type == "z-report":
        result = cast(ZReportResponse, result)
        return ReportBody(kind="keyvalue", pairs=_summary_pairs(
            result.bill_count, result.subtotal, result.discount_amount, result.cgst_amount,
            result.sgst_amount, result.round_off_amount, result.grand_total, result.payments,
        ))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown report_type: {report_type}")


def report_body_to_grid(body: ReportBody) -> tuple[list[str], list[list[str]]]:
    """Flattens a `ReportBody` into a plain header/row grid for CSV/Excel/PDF export —
    the same column set the printer version already uses (production feedback round 4).
    Print-only concerns (bold/double-height styling, Tamil rasterization) don't apply to
    a text-based export format, so they're simply dropped here — `body.rows` always
    carries the plain English text for every row regardless of `body.tamil_names` (that
    dict only tells the *thermal* renderer which rows to additionally rasterize; it never
    mutates the row's own text — see `ReportBody`'s docstring, printing/base.py).
    """
    if body.kind == "keyvalue":
        return ["Field", "Value"], [[label, value] for label, value in body.pairs]
    return body.headers, body.rows


async def _closed_by_label(session: AsyncSession, user_id: uuid.UUID) -> str:
    """"Closed By: <name> (<role>)" for the Z-Report's own print — the tenant_admin or
    Cashier currently logged in and printing it, i.e. who actually closed this shift.
    """
    row = (
        await session.execute(
            select(User.name, Role.code).join(Role, Role.id == User.role_id).where(User.id == user_id)
        )
    ).one()
    name, role_code = row
    role_label = _CLOSER_ROLE_LABELS.get(role_code, role_code)
    return f"Closed By: {name} ({role_label})"


async def render_report_print_bytes(
    session: AsyncSession,
    tenant: Tenant,
    req: ReportPrintRequest,
    printer: Printer,
    current_user_id: uuid.UUID,
) -> bytes:
    """Mirrors each `/reports/*` GET endpoint's own export block (reports.py) — same
    `report_service` call, then `build_report_body` for the exact same column shape —
    but wrapped into a `ReportRenderData` for `dispatch_report_print` (printer_type-aware
    ESC/POS vs plain dot-matrix text) instead of a CSV/Excel/PDF grid. The per-report-type
    branch here only decides *which* `report_service` function to call and how to build
    `extra_header_lines` (Z-Report's own "Shift Close Time"/"Closed By") — the actual
    column-shaping is `build_report_body`'s job, shared with the export path.
    """
    title = REPORT_TITLES[req.report_type]
    # No "Printed:" label prefix — just the date and time (production feedback round 3).
    printed_at_label = now_ist().strftime("%d-%b-%Y %I:%M %p")
    branch = await resolve_branch_header(session, printer.location_id)
    extra_header_lines: list[str] = []

    if req.report_type == "z-report":
        if req.report_date is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "report_date is required for z-report")
        params = ReportQueryParams(
            date_from=req.report_date, date_to=req.report_date, location_id=req.location_id
        )
        result = await report_service.z_report(session, tenant.id, params)
        shift_time = now_ist().strftime("%I:%M %p")
        extra_header_lines = [
            f"Shift Close Time: {result.report_date.strftime('%d-%b-%Y')} {shift_time}",
            await _closed_by_label(session, current_user_id),
        ]
        body = build_report_body(req.report_type, result, tenant.report_tamil_names_enabled)
    elif req.report_type == "item-list":
        # No date range or location scope — a snapshot of the current item catalog, not
        # a sales figure (report_service.item_list). Its print body is deliberately not
        # built via build_report_body — see item_list_print_body's own docstring.
        item_list_result = await report_service.item_list(session, tenant.id)
        body = item_list_print_body(item_list_result.rows)
    else:
        if req.date_from is None or req.date_to is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_from and date_to are required")
        params = ReportQueryParams(date_from=req.date_from, date_to=req.date_to, location_id=req.location_id)

        if req.report_type == "sales-summary":
            result = await report_service.sales_summary(session, tenant.id, params)
        elif req.report_type == "item-wise":
            result = await report_service.item_wise_sales(session, tenant.id, params)
        elif req.report_type == "category-wise":
            result = await report_service.category_wise_sales(session, tenant.id, params)
        elif req.report_type == "order-type-wise":
            result = await report_service.order_type_wise_sales(session, tenant.id, params)
        elif req.report_type == "tax-summary":
            result = await report_service.tax_summary(session, tenant.id, params)
        elif req.report_type == "waiter-wise":
            result = await report_service.waiter_wise_sales(session, tenant.id, params)
        elif req.report_type == "cashier-wise":
            result = await report_service.cashier_wise_sales(session, tenant.id, params)
        elif req.report_type == "pos-operator-wise":
            result = await report_service.pos_operator_wise_sales(session, tenant.id, params)
        elif req.report_type == "waiter-incentive":
            result = await report_service.waiter_incentive_report(session, tenant.id, params)
        elif req.report_type == "cashier-incentive":
            result = await report_service.cashier_incentive_report(session, tenant.id, params)
        elif req.report_type == "pos-operator-incentive":
            result = await report_service.pos_operator_incentive_report(session, tenant.id, params)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown report_type: {req.report_type}")

        body = build_report_body(req.report_type, result, tenant.report_tamil_names_enabled)

    data = ReportRenderData(
        title=title,
        printed_at_label=printed_at_label,
        extra_header_lines=extra_header_lines,
        branch_name=branch.name,
        branch_address_lines=branch.address_lines,
        branch_gstin=branch.gstin,
        paper_width_mm=printer.paper_width_mm,
        body=body,
    )
    return dispatch_report_print(printer, data)
