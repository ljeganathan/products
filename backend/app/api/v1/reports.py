import csv
import io
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.plan_limits import feature_enabled
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.report_repository import ReportRepository
from app.schemas.report import GstSummaryOut, SalesReportDayOut, SalesReportOut
from app.utils.currency import paise_to_plain_amount

router = APIRouter(prefix="/reports", tags=["reports"])

require_staff = require_role(UserRole.ADMIN, UserRole.POS_USER)

# Reports reuse the same "dashboard_range" flag as /dashboard/trend and
# /dashboard/breakdown (Pro/Pro Max) — docs/SUBSCRIPTION_TIERS.md bundles
# "date-range sales, GST summary, CSV export" together under one Pro+
# capability rather than listing a separate flag for reports.
CSV_UPGRADE_MESSAGE = "CSV export is a Pro/Pro Max feature. Upgrade your plan to use this."


def _effective_cashier_id(
    current_user: CurrentUser, cashier_id: uuid.UUID | None
) -> uuid.UUID | None:
    return current_user.user_id if current_user.role == UserRole.POS_USER else cashier_id


async def _resolve_range(
    db: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> tuple[date, date, bool]:
    """Lite plan gets today-only reports — silently clamped rather than
    rejected, mirroring bill search's saved_bill_days clamp
    (api/v1/bills.py)."""
    if await feature_enabled(db, tenant_id, "dashboard_range"):
        return date_from, date_to, False
    today = date.today()
    clamped = date_from != today or date_to != today
    return today, today, clamped


@router.get("/sales", response_model=SalesReportOut)
async def get_sales_report(
    date_from: date = Query(default_factory=date.today),
    date_to: date = Query(default_factory=date.today),
    store_id: uuid.UUID | None = Query(None),
    cashier_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> SalesReportOut:
    assert current_user.tenant_id is not None
    effective_from, effective_to, clamped = await _resolve_range(
        db, current_user.tenant_id, date_from, date_to
    )
    scoped_store_id = store_id or current_user.store_id
    effective_cashier_id = _effective_cashier_id(current_user, cashier_id)

    report = await ReportRepository(db).get_sales_report(
        current_user.tenant_id, scoped_store_id, effective_cashier_id, effective_from, effective_to
    )
    return SalesReportOut(
        date_from=effective_from,
        date_to=effective_to,
        range_clamped=clamped,
        total_paise=report["total_paise"],
        bill_count=report["bill_count"],
        avg_bill_paise=report["avg_bill_paise"],
        daily=[SalesReportDayOut(**d) for d in report["daily"]],
    )


@router.get("/gst-summary", response_model=GstSummaryOut)
async def get_gst_summary(
    date_from: date = Query(default_factory=date.today),
    date_to: date = Query(default_factory=date.today),
    store_id: uuid.UUID | None = Query(None),
    cashier_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> GstSummaryOut:
    assert current_user.tenant_id is not None
    effective_from, effective_to, clamped = await _resolve_range(
        db, current_user.tenant_id, date_from, date_to
    )
    scoped_store_id = store_id or current_user.store_id
    effective_cashier_id = _effective_cashier_id(current_user, cashier_id)

    summary = await ReportRepository(db).get_gst_summary(
        current_user.tenant_id, scoped_store_id, effective_cashier_id, effective_from, effective_to
    )
    return GstSummaryOut(
        date_from=effective_from, date_to=effective_to, range_clamped=clamped, **summary
    )


@router.get("/sales.csv")
async def export_sales_csv(
    date_from: date = Query(default_factory=date.today),
    date_to: date = Query(default_factory=date.today),
    store_id: uuid.UUID | None = Query(None),
    cashier_id: uuid.UUID | None = Query(None),
    current_user: CurrentUser = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
) -> Response:
    assert current_user.tenant_id is not None
    if not await feature_enabled(db, current_user.tenant_id, "dashboard_range"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CSV_UPGRADE_MESSAGE)

    scoped_store_id = store_id or current_user.store_id
    effective_cashier_id = _effective_cashier_id(current_user, cashier_id)
    rows = await ReportRepository(db).list_sales_rows_for_csv(
        current_user.tenant_id, scoped_store_id, effective_cashier_id, date_from, date_to
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Bill #",
            "Date",
            "Cashier",
            "Customer",
            "Subtotal",
            "Discount",
            "CGST",
            "SGST",
            "Round off",
            "Total",
            "Payment mode",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["bill_number"],
                row["created_at"].isoformat(),
                row["cashier_name"],
                row["customer_name"] or "",
                paise_to_plain_amount(row["subtotal_paise"]),
                paise_to_plain_amount(row["discount_paise"]),
                paise_to_plain_amount(row["cgst_paise"]),
                paise_to_plain_amount(row["sgst_paise"]),
                paise_to_plain_amount(row["round_off_paise"]),
                paise_to_plain_amount(row["total_paise"]),
                row["payment_mode"].value,
            ]
        )

    filename = f"sales-{date_from.isoformat()}-{date_to.isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
