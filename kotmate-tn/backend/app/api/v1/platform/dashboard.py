from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.platform import DashboardAlertsResponse
from app.services.invoicing import get_dashboard_alerts

router = APIRouter(prefix="/dashboard", tags=["platform-dashboard"])


@router.get("/alerts", response_model=DashboardAlertsResponse)
async def get_dashboard_alerts_endpoint(db: AsyncSession = Depends(get_db)) -> DashboardAlertsResponse:
    return await get_dashboard_alerts(db)
