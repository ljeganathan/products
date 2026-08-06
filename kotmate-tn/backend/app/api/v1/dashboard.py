import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.dashboard import DashboardSummaryResponse, MultiLocationComparisonResponse
from app.services.dashboard_service import dashboard_summary, multi_location_comparison
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
