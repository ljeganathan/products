import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    HourlyItemBreakdownResponse,
    LowStockItemsResponse,
    MultiLocationComparisonResponse,
    SalesTrendResponse,
)
from app.services.dashboard_service import (
    dashboard_summary,
    hourly_item_breakdown,
    low_stock_items,
    multi_location_comparison,
    sales_trend,
)
from app.services.stock_service import is_stock_tracking_enabled
from app.services.tenant_onboarding import get_active_plan

# Same access rule as reports (CLAUDE.md §5) — waiter has no dashboard/reports access.
router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_tenant_scope), Depends(require_role("tenant_admin", "pos_user"))],
)


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    report_date: date | None = None,
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryResponse:
    """Basic KPIs are available on every plan tier (CLAUDE.md §6) — no gating here; the
    frontend decides whether to render `hourly_trend` as a chart based on the plan.
    """
    return await dashboard_summary(db, current_user.tenant_id, report_date or date.today(), location_id)


@router.get("/hourly-items", response_model=HourlyItemBreakdownResponse)
async def get_hourly_item_breakdown(
    hour: int,
    report_date: date | None = None,
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HourlyItemBreakdownResponse:
    """Item-level drilldown for a single bar of the Hourly Sales Trend chart — same
    no-extra-gating convention as `/summary` (basic KPIs, every plan tier); the
    frontend only renders the chart (and so only ever calls this) once it's already
    decided the tenant's plan has charts.
    """
    if not 0 <= hour <= 23:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "hour must be between 0 and 23")
    return await hourly_item_breakdown(
        db, current_user.tenant_id, report_date or date.today(), location_id, hour
    )


@router.get("/low-stock-items", response_model=LowStockItemsResponse)
async def get_low_stock_items(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LowStockItemsResponse:
    """Every plan tier (basic soft-inventory awareness, CLAUDE.md §11) — items aren't
    location-scoped so there's no `location_id` filter, unlike `/summary`. Silently
    empty (not a 403) when the effective flag is off, matching a Pro/Pro Max tenant
    turning their switch off — a quiet dashboard widget, not an error.
    """
    tenant = (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()
    plan = await get_active_plan(db, current_user.tenant_id)
    if not is_stock_tracking_enabled(tenant, plan.features if plan else None):
        return LowStockItemsResponse(rows=[])
    return await low_stock_items(db, current_user.tenant_id)


@router.get(
    "/sales-trend",
    response_model=SalesTrendResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def get_sales_trend(
    period: str,
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SalesTrendResponse:
    """tenant_admin-only (production feedback) — enforced here, not just hidden on the
    frontend, matching CLAUDE.md's usual role-gating convention (e.g. §5/§9 for waiter
    billing). Available on every plan tier, same as the rest of the basic dashboard.
    """
    if period not in ("monthly", "yearly"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "period must be 'monthly' or 'yearly'")
    return await sales_trend(db, current_user.tenant_id, period, location_id)


@router.get("/multi-location", response_model=MultiLocationComparisonResponse)
async def get_multi_location_comparison(
    date_from: date,
    date_to: date,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MultiLocationComparisonResponse:
    plan = await get_active_plan(db, current_user.tenant_id)
    if not plan or plan.features.get("reports") != "charts_csv_pdf_excel_multilocation":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Multi-location comparison is a Pro Max feature. Upgrade to unlock it.",
        )
    return await multi_location_comparison(db, current_user.tenant_id, date_from, date_to)
