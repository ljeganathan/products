import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Printer, Role, Tenant, User
from app.printing.base import _PAYMENT_LABELS, ReportBody, ReportRenderData, format_inr, now_ist
from app.printing.dispatcher import dispatch_report_print
from app.schemas.report_print import ReportPrintRequest
from app.schemas.reports import (
    CategoryWiseSalesRow,
    ItemWiseSalesRow,
    PaymentMethodTotal,
    ReportQueryParams,
)
from app.services import report_service
from app.services.branch_header import resolve_branch_header

# Reports (and so Z-Report's "Closed By" line) are only ever printed by a tenant_admin
# or pos_user/Cashier — reports.py's router requires one of those two roles — so this
# only needs to cover the two labels a shift-closer can actually have.
_CLOSER_ROLE_LABELS = {"tenant_admin": "Admin", "pos_user": "Cashier"}

_TITLES = {
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


def _item_or_category_body(
    rows_data: list[ItemWiseSalesRow] | list[CategoryWiseSalesRow],
    tenant: Tenant,
    total_revenue: float,
) -> ReportBody:
    """Item Wise Sales and Category Wise Sales reduce to the exact same shape — one Name
    column (was two: name_en + name_ta), "Qty"/"Sales" headers, no "Rs." on amounts, and
    a bold+double-height TOTAL row (production feedback round 3).

    `rows[i][0]` is always the English name — needed as-is by the dot-matrix adapter
    (which has no image support and so always falls back to English, CLAUDE.md §10) and
    as the base row the thermal adapter blanks when it prints a rasterized Tamil line
    instead (see ReportBody's own docstring, printing/base.py). Only `tamil_names` (built
    here from `tenant.report_tamil_names_enabled`) tells the thermal adapter which rows
    should show Tamil at all.
    """
    headers = ["Name", "Qty", "Sales"]
    rows: list[list[str]] = []
    tamil_names: dict[int, str] = {}
    for idx, r in enumerate(rows_data):
        rows.append([r.name_en, str(r.quantity_sold), _amount(r.revenue)])
        if tenant.report_tamil_names_enabled and r.name_ta:
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
    `report_service` call, same row model — but built into a `ReportRenderData` for
    `dispatch_report_print` (printer_type-aware ESC/POS vs plain dot-matrix text)
    instead of the generic CSV/Excel/PDF grid `export_service` produces. Kept as one flat
    if/elif per report_type, matching reports.py's own repetitive-by-design shape.
    """
    title = _TITLES[req.report_type]
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
        body = ReportBody(
            kind="keyvalue",
            pairs=_summary_pairs(
                result.bill_count,
                result.subtotal,
                result.discount_amount,
                result.cgst_amount,
                result.sgst_amount,
                result.round_off_amount,
                result.grand_total,
                result.payments,
            ),
        )
    else:
        if req.date_from is None or req.date_to is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_from and date_to are required")
        params = ReportQueryParams(date_from=req.date_from, date_to=req.date_to, location_id=req.location_id)

        if req.report_type == "sales-summary":
            result = await report_service.sales_summary(session, tenant.id, params)
            body = ReportBody(
                kind="keyvalue",
                pairs=_summary_pairs(
                    result.bill_count,
                    result.subtotal,
                    result.discount_amount,
                    result.cgst_amount,
                    result.sgst_amount,
                    result.round_off_amount,
                    result.grand_total,
                    result.payments,
                ),
            )
        elif req.report_type == "item-wise":
            result = await report_service.item_wise_sales(session, tenant.id, params)
            body = _item_or_category_body(result.rows, tenant, result.total_revenue)
        elif req.report_type == "category-wise":
            result = await report_service.category_wise_sales(session, tenant.id, params)
            body = _item_or_category_body(result.rows, tenant, result.total_revenue)
        elif req.report_type == "tax-summary":
            result = await report_service.tax_summary(session, tenant.id, params)
            body = ReportBody(
                kind="keyvalue",
                pairs=[
                    ("Taxable Value", _amount(result.taxable_value)),
                    ("CGST", _amount(result.cgst_amount)),
                    ("SGST", _amount(result.sgst_amount)),
                    ("Total Tax", _amount(result.total_tax)),
                ],
            )
        elif req.report_type == "waiter-wise":
            result = await report_service.waiter_wise_sales(session, tenant.id, params)
            rows = [(r.waiter_name, r.bill_count, r.net_sale_value) for r in result.rows]
            headers = ["Waiter Name", "Bill Count", "Sales"]
            body = _sales_grid_body(headers, rows, "TOTAL", result.total_net_sale_value)
        elif req.report_type == "cashier-wise":
            result = await report_service.cashier_wise_sales(session, tenant.id, params)
            rows = [(r.name, r.bill_count, r.net_sale_value) for r in result.rows]
            headers = ["Cashier Name", "Bill Count", "Sales"]
            body = _sales_grid_body(headers, rows, "TOTAL", result.total_net_sale_value)
        elif req.report_type == "pos-operator-wise":
            result = await report_service.pos_operator_wise_sales(session, tenant.id, params)
            rows = [(r.name, r.bill_count, r.net_sale_value) for r in result.rows]
            headers = ["Name", "Bill Count", "Sales"]
            body = _sales_grid_body(headers, rows, "TOTAL", result.total_net_sale_value)
        elif req.report_type == "waiter-incentive":
            result = await report_service.waiter_incentive_report(session, tenant.id, params)
            rows = [(r.waiter_name, r.net_sale_value, r.incentive_amount) for r in result.rows]
            body = _incentive_grid_body(
                ["Waiter Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
            )
        elif req.report_type == "cashier-incentive":
            result = await report_service.cashier_incentive_report(session, tenant.id, params)
            rows = [(r.name, r.net_sale_value, r.incentive_amount) for r in result.rows]
            body = _incentive_grid_body(
                ["Cashier Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
            )
        elif req.report_type == "pos-operator-incentive":
            result = await report_service.pos_operator_incentive_report(session, tenant.id, params)
            rows = [(r.name, r.net_sale_value, r.incentive_amount) for r in result.rows]
            body = _incentive_grid_body(
                ["Name", "Net Sales", "Incentive Amt"], rows, "TOTAL", result.total_incentive_amount
            )
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown report_type: {req.report_type}")

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
