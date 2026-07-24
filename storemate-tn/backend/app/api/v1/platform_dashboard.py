from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.models.enums import UserRole
from app.repositories.platform_dashboard_repository import PlatformDashboardRepository
from app.schemas.platform_dashboard import PlanMixOut, PlatformDashboardOut

router = APIRouter(prefix="/platform/dashboard", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)


@router.get("", response_model=PlatformDashboardOut)
async def get_platform_dashboard(
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PlatformDashboardOut:
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    data = await PlatformDashboardRepository(db).get_dashboard(month_start=month_start)
    return PlatformDashboardOut(
        active_tenant_count=data["active_tenant_count"],
        trialing_count=data["trialing_count"],
        churned_this_month_count=data["churned_this_month_count"],
        mrr_paise=data["mrr_paise"],
        plan_mix=[PlanMixOut(**p) for p in data["plan_mix"]],
        overdue_invoices_count=data["overdue_invoices_count"],
    )
