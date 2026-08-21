import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bill, BillItem, TenantLocation
from app.schemas.dashboard import (
    DashboardSummaryResponse,
    HourlySalesPoint,
    LocationComparisonRow,
    LowStockItemRow,
    LowStockItemsResponse,
    MultiLocationComparisonResponse,
    SalesTrendPoint,
    SalesTrendResponse,
    TopItemRow,
)
from app.services.item_service import list_low_stock_items

# India-only product (CLAUDE.md: Tamil Nadu) — hardcoding IST rather than adding a
# per-tenant timezone setting nobody has asked for, so "hourly trend" lines up with an
# actual lunch/dinner rush instead of a UTC-shifted one.
_IST = "Asia/Kolkata"


def _day_filters(tenant_id: uuid.UUID, report_date: date, location_id: uuid.UUID | None) -> list:
    filters = [
        Bill.tenant_id == tenant_id,
        Bill.status == "finalized",
        Bill.created_at >= report_date,
        Bill.created_at < report_date + timedelta(days=1),
    ]
    if location_id is not None:
        filters.append(Bill.location_id == location_id)
    return filters


async def dashboard_summary(
    session: AsyncSession, tenant_id: uuid.UUID, report_date: date, location_id: uuid.UUID | None
) -> DashboardSummaryResponse:
    filters = _day_filters(tenant_id, report_date, location_id)

    totals = (
        await session.execute(
            select(func.count(Bill.id), func.coalesce(func.sum(Bill.grand_total), 0)).where(*filters)
        )
    ).one()
    bill_count, today_sales = totals
    average_bill_value = round(float(today_sales) / bill_count, 2) if bill_count else 0.0

    top_item_rows = (
        await session.execute(
            select(BillItem.item_id, BillItem.name_en_snapshot, func.sum(BillItem.quantity))
            .join(Bill, Bill.id == BillItem.bill_id)
            .where(*filters)
            .group_by(BillItem.item_id, BillItem.name_en_snapshot)
            # Ordered by units sold (matches the `quantity_sold` field below), not
            # revenue — production feedback: "top selling item count should be
            # descending order".
            .order_by(func.sum(BillItem.quantity).desc())
            .limit(5)
        )
    ).all()
    top_items = [
        TopItemRow(item_id=item_id, name_en=name_en, quantity_sold=int(qty))
        for item_id, name_en, qty in top_item_rows
    ]

    hour_expr = func.extract("hour", func.timezone(_IST, Bill.created_at))
    hourly_rows = (
        await session.execute(
            select(hour_expr, func.sum(Bill.grand_total)).where(*filters).group_by(hour_expr)
        )
    ).all()
    sales_by_hour = {int(hour): float(sales) for hour, sales in hourly_rows}
    hourly_trend = [HourlySalesPoint(hour=h, sales=sales_by_hour.get(h, 0.0)) for h in range(24)]

    return DashboardSummaryResponse(
        report_date=report_date,
        today_sales=float(today_sales),
        bill_count=bill_count,
        average_bill_value=average_bill_value,
        top_items=top_items,
        hourly_trend=hourly_trend,
    )


def _month_start(d: date) -> date:
    return date(d.year, d.month, 1)


def _add_months(d: date, months: int) -> date:
    total = d.year * 12 + (d.month - 1) + months
    return date(total // 12, total % 12 + 1, 1)


async def sales_trend(
    session: AsyncSession, tenant_id: uuid.UUID, period: str, location_id: uuid.UUID | None
) -> SalesTrendResponse:
    """Admin-only "Monthly Sales Trend" chart (production feedback) — `period="monthly"`
    is a rolling 30-day window bucketed by day, `period="yearly"` is a rolling 12-month
    window (by calendar month, not by day) bucketed by month. Both are trailing windows
    ending today/this month, not a fixed "this calendar month/year" — matches how the
    tenant asked for it ("monthly means 30 days ... yearly means 12 months").
    """
    today = date.today()
    if period == "yearly":
        start = _add_months(_month_start(today), -11)
    else:
        start = today - timedelta(days=29)

    filters = [
        Bill.tenant_id == tenant_id,
        Bill.status == "finalized",
        Bill.created_at >= start,
        Bill.created_at < today + timedelta(days=1),
    ]
    if location_id is not None:
        filters.append(Bill.location_id == location_id)

    if period == "yearly":
        bucket_expr = func.date_trunc("month", func.timezone(_IST, Bill.created_at))
        query = select(bucket_expr, func.sum(Bill.grand_total)).where(*filters).group_by(bucket_expr)
        rows = (await session.execute(query)).all()
        sales_by_month = {
            (bucket.year, bucket.month): float(total)
            for bucket, total in rows
            if isinstance(bucket, datetime)
        }
        points = []
        cursor = start
        for _ in range(12):
            points.append(
                SalesTrendPoint(
                    label=cursor.strftime("%b %Y"), sales=sales_by_month.get((cursor.year, cursor.month), 0.0)
                )
            )
            cursor = _add_months(cursor, 1)
        return SalesTrendResponse(period=period, points=points)

    bucket_expr = func.date(func.timezone(_IST, Bill.created_at))
    query = select(bucket_expr, func.sum(Bill.grand_total)).where(*filters).group_by(bucket_expr)
    rows = (await session.execute(query)).all()
    sales_by_day = {bucket: float(total) for bucket, total in rows}
    points = []
    for i in range(30):
        d = start + timedelta(days=i)
        points.append(SalesTrendPoint(label=d.strftime("%d %b"), sales=sales_by_day.get(d, 0.0)))
    return SalesTrendResponse(period=period, points=points)


async def low_stock_items(session: AsyncSession, tenant_id: uuid.UUID) -> LowStockItemsResponse:
    items = await list_low_stock_items(session, tenant_id)
    return LowStockItemsResponse(
        rows=[
            LowStockItemRow(
                item_id=item.id, name_en=item.name_en, name_ta=item.name_ta, available_qty=item.available_qty
            )
            for item in items
        ]
    )


async def multi_location_comparison(
    session: AsyncSession, tenant_id: uuid.UUID, date_from: date, date_to: date
) -> MultiLocationComparisonResponse:
    """Pro Max only (CLAUDE.md §6) — enforced by the caller (route), not here; this
    function just computes across every location, deliberately ignoring any single
    `location_id` filter since the entire point is comparing them.
    """
    rows = (
        await session.execute(
            select(
                TenantLocation.id,
                TenantLocation.name,
                func.coalesce(func.sum(Bill.grand_total), 0),
                func.count(Bill.id),
            )
            .join(Bill, Bill.location_id == TenantLocation.id)
            .where(
                Bill.tenant_id == tenant_id,
                Bill.status == "finalized",
                Bill.created_at >= date_from,
                Bill.created_at < date_to + timedelta(days=1),
            )
            .group_by(TenantLocation.id, TenantLocation.name)
            .order_by(func.sum(Bill.grand_total).desc())
        )
    ).all()
    return MultiLocationComparisonResponse(
        rows=[
            LocationComparisonRow(
                location_id=loc_id, location_name=name, sales=float(sales), bill_count=count
            )
            for loc_id, name, sales, count in rows
        ]
    )
