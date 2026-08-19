import base64
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Printer, Tenant
from app.printing.network_transport import send_raw_bytes_over_network
from app.schemas.printing import PrintJobPayload
from app.schemas.report_print import ReportPrintRequest, ReportPrintResponse
from app.schemas.reports import (
    CashierIncentiveResponse,
    CashierIncentiveRow,
    CashierSalesResponse,
    CashierSalesRow,
    CategoryWiseSalesResponse,
    CategoryWiseSalesRow,
    ItemWiseSalesResponse,
    ItemWiseSalesRow,
    PosOperatorIncentiveResponse,
    PosOperatorIncentiveRow,
    PosOperatorSalesResponse,
    PosOperatorSalesRow,
    ReportQueryParams,
    SalesSummaryResponse,
    TaxSummaryResponse,
    WaiterIncentiveResponse,
    WaiterIncentiveRow,
    WaiterSalesResponse,
    WaiterSalesRow,
    ZReportResponse,
)
from app.services import report_service
from app.services.export_service import export_rows
from app.services.report_print_service import (
    is_report_printing_enabled,
    render_report_print_bytes,
)
from app.services.tenant_onboarding import get_active_plan

# Reports are tenant_admin/pos_user only — a `waiter` has no reports access at all
# (CLAUDE.md §5), enforced once here for the whole router, mirroring bills.py.
router = APIRouter(
    prefix="/reports",
    tags=["reports"],
    dependencies=[Depends(require_tenant_scope), Depends(require_role("tenant_admin", "pos_user"))],
)


async def _require_export_format(db: AsyncSession, tenant_id: uuid.UUID, export: str) -> None:
    plan = await get_active_plan(db, tenant_id)
    allowed = (plan.features.get("export_formats") if plan else None) or []
    if export not in allowed:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Exporting to {export} isn't available on your current plan. Upgrade to unlock it.",
        )


def _file_response(content: bytes, media_type: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _params(date_from: date, date_to: date, location_id: uuid.UUID | None) -> ReportQueryParams:
    return ReportQueryParams(date_from=date_from, date_to=date_to, location_id=location_id)


@router.get("/sales-summary", response_model=SalesSummaryResponse)
async def get_sales_summary(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesSummaryResponse | Response:
    params = _params(date_from, date_to, location_id)
    result = await report_service.sales_summary(db, current_user.tenant_id, params)
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Sales Summary", SalesSummaryResponse, [result], export
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/item-wise", response_model=ItemWiseSalesResponse)
async def get_item_wise_sales(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ItemWiseSalesResponse | Response:
    result = await report_service.item_wise_sales(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Item Wise Sales",
            ItemWiseSalesRow,
            result.rows,
            export,
            totals_row={"name_en": "TOTAL", "revenue": result.total_revenue},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/category-wise", response_model=CategoryWiseSalesResponse)
async def get_category_wise_sales(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryWiseSalesResponse | Response:
    result = await report_service.category_wise_sales(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Category Wise Sales",
            CategoryWiseSalesRow,
            result.rows,
            export,
            totals_row={"name_en": "TOTAL", "revenue": result.total_revenue},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/tax-summary", response_model=TaxSummaryResponse)
async def get_tax_summary(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaxSummaryResponse | Response:
    params = _params(date_from, date_to, location_id)
    result = await report_service.tax_summary(db, current_user.tenant_id, params)
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows("Tax Summary", TaxSummaryResponse, [result], export)
        return _file_response(content, media_type, filename)
    return result


@router.get("/waiter-wise", response_model=WaiterSalesResponse)
async def get_waiter_wise_sales(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterSalesResponse | Response:
    result = await report_service.waiter_wise_sales(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Waiter Wise Sales",
            WaiterSalesRow,
            result.rows,
            export,
            totals_row={"waiter_name": "TOTAL", "net_sale_value": result.total_net_sale_value},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/cashier-wise", response_model=CashierSalesResponse)
async def get_cashier_wise_sales(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashierSalesResponse | Response:
    result = await report_service.cashier_wise_sales(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Cashier Wise Sales",
            CashierSalesRow,
            result.rows,
            export,
            totals_row={"name": "TOTAL", "net_sale_value": result.total_net_sale_value},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/waiter-incentive", response_model=WaiterIncentiveResponse)
async def get_waiter_incentive_report(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterIncentiveResponse | Response:
    result = await report_service.waiter_incentive_report(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Waiter Incentive",
            WaiterIncentiveRow,
            result.rows,
            export,
            totals_row={"waiter_name": "TOTAL", "incentive_amount": result.total_incentive_amount},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/cashier-incentive", response_model=CashierIncentiveResponse)
async def get_cashier_incentive_report(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CashierIncentiveResponse | Response:
    result = await report_service.cashier_incentive_report(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "Cashier Incentive",
            CashierIncentiveRow,
            result.rows,
            export,
            totals_row={"name": "TOTAL", "incentive_amount": result.total_incentive_amount},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/pos-operator-wise", response_model=PosOperatorSalesResponse)
async def get_pos_operator_wise_sales(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PosOperatorSalesResponse | Response:
    result = await report_service.pos_operator_wise_sales(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "POS Operator Wise Sales",
            PosOperatorSalesRow,
            result.rows,
            export,
            totals_row={"name": "TOTAL", "net_sale_value": result.total_net_sale_value},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/pos-operator-incentive", response_model=PosOperatorIncentiveResponse)
async def get_pos_operator_incentive_report(
    date_from: date,
    date_to: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PosOperatorIncentiveResponse | Response:
    result = await report_service.pos_operator_incentive_report(
        db, current_user.tenant_id, _params(date_from, date_to, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        content, media_type, filename = export_rows(
            "POS Operator Incentive",
            PosOperatorIncentiveRow,
            result.rows,
            export,
            totals_row={"name": "TOTAL", "incentive_amount": result.total_incentive_amount},
        )
        return _file_response(content, media_type, filename)
    return result


@router.get("/z-report", response_model=ZReportResponse)
async def get_z_report(
    report_date: date,
    location_id: uuid.UUID | None = None,
    export: str | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ZReportResponse | Response:
    result = await report_service.z_report(
        db, current_user.tenant_id, _params(report_date, report_date, location_id)
    )
    if export:
        await _require_export_format(db, current_user.tenant_id, export)
        # `payments` is a list of sub-objects — flatten it to a readable string for the
        # exported file rather than letting the generic exporter stringify raw Pydantic
        # objects into the cell.
        payments_summary = ", ".join(f"{p.method}: {p.amount:.2f}" for p in result.payments)
        export_row = result.model_copy(update={"payments": payments_summary})
        content, media_type, filename = export_rows("Z Report", ZReportResponse, [export_row], export)
        return _file_response(content, media_type, filename)
    return result


@router.post("/print", response_model=ReportPrintResponse)
async def print_report(
    payload: ReportPrintRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportPrintResponse:
    """Pro Max only, and only when the tenant has switched the toggle on (Settings >
    Preferences) — same tenant-level kill-switch shape as stock_management_enabled.
    Renders plain ESC/POS-safe text (report_print_service), not the PDF/Excel/CSV
    export — a thermal/dot-matrix printer can't render a PDF.
    """
    tenant = (
        await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    ).scalar_one()
    plan = await get_active_plan(db, current_user.tenant_id)
    if not is_report_printing_enabled(tenant, plan.features if plan else None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Report printing isn't enabled for your account — a tenant_admin can turn it on in "
            "Settings > Preferences (Pro Max only).",
        )

    printer_query = select(Printer).where(
        Printer.tenant_id == current_user.tenant_id,
        Printer.target == "reports",
        Printer.is_active.is_(True),
    )
    if payload.location_id is not None:
        printer_query = printer_query.where(Printer.location_id == payload.location_id)
    printer = (await db.execute(printer_query)).scalars().first()
    if printer is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No active Reports printer is registered for this location — add one in Settings > Printers.",
        )

    content = await render_report_print_bytes(db, tenant, payload, printer, current_user.id)

    # Same usb/local_agent/bluetooth/rawbt (frontend-dispatched) vs network/wifi
    # (backend-dispatched) split as bill/KOT printing (bill_service._dispatch_print_for_bill).
    if printer.connection_type in ("usb", "local_agent", "bluetooth", "rawbt"):
        return ReportPrintResponse(
            printed=True,
            print_job=PrintJobPayload(
                printer_id=printer.id,
                connection_type=printer.connection_type,
                connection_details=printer.connection_details or {},
                data_base64=base64.b64encode(content).decode("ascii"),
                paper_width_mm=printer.paper_width_mm,
            ),
        )
    if printer.connection_type in ("network", "wifi"):
        details = printer.connection_details or {}
        print_error = send_raw_bytes_over_network(details.get("ip_address"), details.get("port"), content)
        return ReportPrintResponse(printed=print_error is None, print_error=print_error)

    connection_label = printer.connection_type.replace("_", " ").title()
    return ReportPrintResponse(printed=False, print_error=f"{connection_label} printing isn't supported yet.")
