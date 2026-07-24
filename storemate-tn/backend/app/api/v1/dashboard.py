import uuid
from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import feature_enabled
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.tenant_repository import TenantRepository
from app.schemas.dashboard import (
    BreakdownRowOut,
    DashboardSummaryOut,
    StoreTotalOut,
    TopItemOut,
    TrendPointOut,
)
from app.services.dashboard_export_service import render_dashboard_pdf

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

require_admin = require_role(UserRole.ADMIN)

RANGE_UPGRADE_MESSAGE = (
    "Date-range dashboards, trend charts, and breakdowns are a Pro/Pro Max feature. "
    "Upgrade your plan to use this."
)
MULTISTORE_UPGRADE_MESSAGE = (
    "Multi-store dashboards and PDF export are a Pro Max feature. Upgrade your plan to use this."
)


async def _require_range_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    if not await feature_enabled(db, tenant_id, "dashboard_range"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=RANGE_UPGRADE_MESSAGE)


async def _require_multistore_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    if not await feature_enabled(db, tenant_id, "multi_store"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=MULTISTORE_UPGRADE_MESSAGE
        )


@router.get("/summary", response_model=DashboardSummaryOut)
async def get_dashboard_summary(
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummaryOut:
    assert current_user.tenant_id is not None
    scoped_store_id = store_id or current_user.store_id
    repo = DashboardRepository(db)
    summary = await repo.get_summary(current_user.tenant_id, scoped_store_id, date.today())

    low_stock_count = 0
    if await feature_enabled(db, current_user.tenant_id, "low_stock_alerts"):
        low_stock_count = await repo.get_low_stock_count(current_user.tenant_id, scoped_store_id)

    return DashboardSummaryOut(
        total_paise=summary["total_paise"],
        bill_count=summary["bill_count"],
        avg_bill_paise=summary["avg_bill_paise"],
        top_items=[TopItemOut(**i) for i in summary["top_items"]],
        low_stock_count=low_stock_count,
    )


@router.get("/trend", response_model=list[TrendPointOut])
async def get_dashboard_trend(
    date_from: date = Query(...),
    date_to: date = Query(...),
    group_by: Literal["day", "hour"] = Query("day"),
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TrendPointOut]:
    assert current_user.tenant_id is not None
    await _require_range_feature(db, current_user.tenant_id)
    scoped_store_id = store_id or current_user.store_id
    rows = await DashboardRepository(db).get_trend(
        current_user.tenant_id, scoped_store_id, date_from, date_to, group_by
    )
    return [TrendPointOut(**r) for r in rows]


@router.get("/breakdown", response_model=list[BreakdownRowOut])
async def get_dashboard_breakdown(
    by: Literal["category", "cashier", "payment_mode"] = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    store_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[BreakdownRowOut]:
    assert current_user.tenant_id is not None
    await _require_range_feature(db, current_user.tenant_id)
    scoped_store_id = store_id or current_user.store_id
    rows = await DashboardRepository(db).get_breakdown(
        current_user.tenant_id, scoped_store_id, date_from, date_to, by
    )
    return [BreakdownRowOut(**r) for r in rows]


@router.get("/stores", response_model=list[StoreTotalOut])
async def get_dashboard_stores(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[StoreTotalOut]:
    assert current_user.tenant_id is not None
    await _require_multistore_feature(db, current_user.tenant_id)
    rows = await DashboardRepository(db).get_store_totals(
        current_user.tenant_id, date_from, date_to
    )
    return [StoreTotalOut(**r) for r in rows]


@router.get("/export.pdf")
async def export_dashboard_pdf(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Response:
    assert current_user.tenant_id is not None
    await _require_multistore_feature(db, current_user.tenant_id)

    tenant = await TenantRepository(db).get_by_id(current_user.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    repo = DashboardRepository(db)
    summary = await repo.get_summary(current_user.tenant_id, None, date.today())
    store_totals = await repo.get_store_totals(current_user.tenant_id, date_from, date_to)

    pdf_bytes = render_dashboard_pdf(
        tenant_name=tenant.name,
        summary=summary,
        store_totals=store_totals,
        date_from=date_from,
        date_to=date_to,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
    )
    filename = f"dashboard-{date.today().isoformat()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
