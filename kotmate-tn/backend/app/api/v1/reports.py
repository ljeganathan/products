import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.reports import (
    CashierIncentiveResponse,
    CashierIncentiveRow,
    CashierSalesResponse,
    CashierSalesRow,
    CategoryWiseSalesResponse,
    CategoryWiseSalesRow,
    ItemWiseSalesResponse,
    ItemWiseSalesRow,
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
