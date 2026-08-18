import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.printing.report_print import render_report_text
from app.schemas.report_print import ReportPrintRequest
from app.schemas.reports import (
    CashierIncentiveRow,
    CashierSalesRow,
    CategoryWiseSalesRow,
    ItemWiseSalesRow,
    PosOperatorIncentiveRow,
    PosOperatorSalesRow,
    ReportQueryParams,
    SalesSummaryResponse,
    TaxSummaryResponse,
    WaiterIncentiveRow,
    WaiterSalesRow,
    ZReportResponse,
)
from app.services import report_service
from app.services.export_service import rows_as_grid

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


async def render_report_print_text(
    session: AsyncSession, tenant_id: uuid.UUID, req: ReportPrintRequest, paper_width_mm: int | None
) -> bytes:
    """Mirrors each `/reports/*` GET endpoint's own export block (reports.py) — same
    `report_service` call, same row model, same totals_row shape — just rendered as
    plain ESC/POS-safe text (printing.report_print) instead of csv/excel/pdf bytes
    (export_service). Kept as one flat if/elif per report_type, matching the existing
    repetitive-by-design shape of reports.py's own 9 endpoints, rather than introducing
    a cleverer registry that would just move the same per-type specifics elsewhere.
    """
    title = _TITLES[req.report_type]

    if req.report_type == "z-report":
        if req.report_date is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "report_date is required for z-report")
        params = ReportQueryParams(
            date_from=req.report_date, date_to=req.report_date, location_id=req.location_id
        )
        result = await report_service.z_report(session, tenant_id, params)
        payments_summary = ", ".join(f"{p.method}: {p.amount:.2f}" for p in result.payments)
        export_row = result.model_copy(update={"payments": payments_summary})
        headers, grid = rows_as_grid(ZReportResponse, [export_row], None, exclude_id_fields=True)
        return render_report_text(title, headers, grid, paper_width_mm)

    if req.date_from is None or req.date_to is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_from and date_to are required")
    params = ReportQueryParams(date_from=req.date_from, date_to=req.date_to, location_id=req.location_id)

    if req.report_type == "sales-summary":
        result = await report_service.sales_summary(session, tenant_id, params)
        headers, grid = rows_as_grid(SalesSummaryResponse, [result], None, exclude_id_fields=True)
    elif req.report_type == "item-wise":
        result = await report_service.item_wise_sales(session, tenant_id, params)
        headers, grid = rows_as_grid(
            ItemWiseSalesRow,
            result.rows,
            {"name_en": "TOTAL", "revenue": result.total_revenue},
            exclude_id_fields=True,
        )
    elif req.report_type == "category-wise":
        result = await report_service.category_wise_sales(session, tenant_id, params)
        headers, grid = rows_as_grid(
            CategoryWiseSalesRow,
            result.rows,
            {"name_en": "TOTAL", "revenue": result.total_revenue},
            exclude_id_fields=True,
        )
    elif req.report_type == "tax-summary":
        result = await report_service.tax_summary(session, tenant_id, params)
        headers, grid = rows_as_grid(TaxSummaryResponse, [result], None, exclude_id_fields=True)
    elif req.report_type == "waiter-wise":
        result = await report_service.waiter_wise_sales(session, tenant_id, params)
        headers, grid = rows_as_grid(
            WaiterSalesRow,
            result.rows,
            {"waiter_name": "TOTAL", "net_sale_value": result.total_net_sale_value},
            exclude_id_fields=True,
        )
    elif req.report_type == "cashier-wise":
        result = await report_service.cashier_wise_sales(session, tenant_id, params)
        headers, grid = rows_as_grid(
            CashierSalesRow,
            result.rows,
            {"name": "TOTAL", "net_sale_value": result.total_net_sale_value},
            exclude_id_fields=True,
        )
    elif req.report_type == "waiter-incentive":
        result = await report_service.waiter_incentive_report(session, tenant_id, params)
        headers, grid = rows_as_grid(
            WaiterIncentiveRow,
            result.rows,
            {"waiter_name": "TOTAL", "incentive_amount": result.total_incentive_amount},
            exclude_id_fields=True,
        )
    elif req.report_type == "cashier-incentive":
        result = await report_service.cashier_incentive_report(session, tenant_id, params)
        headers, grid = rows_as_grid(
            CashierIncentiveRow,
            result.rows,
            {"name": "TOTAL", "incentive_amount": result.total_incentive_amount},
            exclude_id_fields=True,
        )
    elif req.report_type == "pos-operator-wise":
        result = await report_service.pos_operator_wise_sales(session, tenant_id, params)
        headers, grid = rows_as_grid(
            PosOperatorSalesRow,
            result.rows,
            {"name": "TOTAL", "net_sale_value": result.total_net_sale_value},
            exclude_id_fields=True,
        )
    elif req.report_type == "pos-operator-incentive":
        result = await report_service.pos_operator_incentive_report(session, tenant_id, params)
        headers, grid = rows_as_grid(
            PosOperatorIncentiveRow,
            result.rows,
            {"name": "TOTAL", "incentive_amount": result.total_incentive_amount},
            exclude_id_fields=True,
        )
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown report_type: {req.report_type}")

    return render_report_text(title, headers, grid, paper_width_mm)
