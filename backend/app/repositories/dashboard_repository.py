import uuid
from datetime import date, datetime
from typing import Any, Literal, TypedDict

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill, BillItem
from app.models.category import Category
from app.models.enums import BillStatus
from app.models.item import Item
from app.models.stock import Stock
from app.models.store import Store
from app.models.user import User


class TopItem(TypedDict):
    name: str
    revenue_paise: int


class DashboardSummary(TypedDict):
    total_paise: int
    bill_count: int
    avg_bill_paise: int
    top_items: list[TopItem]


class TrendPoint(TypedDict):
    bucket: datetime
    total_paise: int
    bill_count: int


class BreakdownRow(TypedDict):
    label: str
    total_paise: int
    bill_count: int


class StoreTotal(TypedDict):
    store_id: uuid.UUID
    store_name: str
    total_paise: int
    bill_count: int


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, datetime.min.time()), datetime.combine(day, datetime.max.time())


class DashboardRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_summary(
        self, tenant_id: uuid.UUID, store_id: uuid.UUID | None, day: date
    ) -> DashboardSummary:
        day_start, day_end = _day_bounds(day)
        filters = [
            Bill.tenant_id == tenant_id,
            Bill.status == BillStatus.COMPLETED,
            Bill.created_at >= day_start,
            Bill.created_at <= day_end,
        ]
        if store_id is not None:
            filters.append(Bill.store_id == store_id)

        total_paise, bill_count = (
            await self.db.execute(
                select(func.coalesce(func.sum(Bill.total_paise), 0), func.count()).where(*filters)
            )
        ).one()

        revenue_col = func.sum(BillItem.line_total_paise).label("revenue_paise")
        top_items_result = await self.db.execute(
            select(BillItem.item_name_snapshot, revenue_col)
            .join(Bill, Bill.id == BillItem.bill_id)
            .where(*filters)
            .group_by(BillItem.item_name_snapshot)
            .order_by(revenue_col.desc())
            .limit(5)
        )
        top_items: list[TopItem] = [
            {"name": name, "revenue_paise": int(revenue)}
            for name, revenue in top_items_result.tuples().all()
        ]

        return {
            "total_paise": int(total_paise),
            "bill_count": int(bill_count),
            "avg_bill_paise": round(total_paise / bill_count) if bill_count else 0,
            "top_items": top_items,
        }

    async def get_low_stock_count(self, tenant_id: uuid.UUID, store_id: uuid.UUID | None) -> int:
        filters = [
            Stock.tenant_id == tenant_id,
            Item.is_active.is_(True),
            Stock.quantity_on_hand <= Item.reorder_level,
        ]
        if store_id is not None:
            filters.append(Stock.store_id == store_id)
        count = await self.db.scalar(
            select(func.count())
            .select_from(Stock)
            .join(Item, Item.id == Stock.item_id)
            .where(*filters)
        )
        return count or 0

    async def get_trend(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
        group_by: Literal["day", "hour"],
    ) -> list[TrendPoint]:
        range_start, range_end = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
        filters = [
            Bill.tenant_id == tenant_id,
            Bill.status == BillStatus.COMPLETED,
            Bill.created_at >= range_start,
            Bill.created_at <= range_end,
        ]
        if store_id is not None:
            filters.append(Bill.store_id == store_id)

        # group_by is a Literal["day","hour"] validated by FastAPI/Pydantic
        # before it ever reaches here, so this string is never user-supplied
        # free text — safe to pass straight into date_trunc.
        bucket_col = func.date_trunc(group_by, Bill.created_at).label("bucket")
        revenue_col = func.sum(Bill.total_paise).label("total_paise")
        count_col = func.count(Bill.id).label("bill_count")

        result = await self.db.execute(
            select(bucket_col, revenue_col, count_col)
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col)
        )
        return [
            {"bucket": bucket, "total_paise": int(total), "bill_count": int(count)}
            for bucket, total, count in result.tuples().all()
        ]

    async def get_breakdown(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
        by: Literal["category", "cashier", "payment_mode"],
    ) -> list[BreakdownRow]:
        range_start, range_end = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
        base_filters = [
            Bill.tenant_id == tenant_id,
            Bill.status == BillStatus.COMPLETED,
            Bill.created_at >= range_start,
            Bill.created_at <= range_end,
        ]
        if store_id is not None:
            base_filters.append(Bill.store_id == store_id)

        label_col: Any
        if by == "payment_mode":
            label_col = Bill.payment_mode
            revenue_col = func.sum(Bill.total_paise).label("total_paise")
            count_col = func.count(Bill.id).label("bill_count")
            stmt = (
                select(label_col, revenue_col, count_col)
                .where(*base_filters)
                .group_by(label_col)
                .order_by(revenue_col.desc())
            )
        elif by == "cashier":
            label_col = User.name
            revenue_col = func.sum(Bill.total_paise).label("total_paise")
            count_col = func.count(Bill.id).label("bill_count")
            stmt = (
                select(label_col, revenue_col, count_col)
                .join(User, User.id == Bill.cashier_id)
                .where(*base_filters)
                .group_by(label_col)
                .order_by(revenue_col.desc())
            )
        else:  # category — attributed at the line-item level, not the bill level
            label_col = Category.name_en
            revenue_col = func.sum(BillItem.line_total_paise).label("total_paise")
            count_col = func.count(func.distinct(Bill.id)).label("bill_count")
            stmt = (
                select(label_col, revenue_col, count_col)
                .select_from(Bill)
                .join(BillItem, BillItem.bill_id == Bill.id)
                .join(Item, Item.id == BillItem.item_id)
                .join(Category, Category.id == Item.category_id)
                .where(*base_filters)
                .group_by(label_col)
                .order_by(revenue_col.desc())
            )

        result = await self.db.execute(stmt)
        return [
            # `Bill.payment_mode` comes back as a PaymentMode enum member —
            # plain str() on a `class X(str, Enum)` member returns "X.MEMBER"
            # in Python 3.11+, not the value, so extract `.value` explicitly
            # where the label is an enum (category/cashier labels are
            # already plain strings and have no `.value`).
            {
                "label": label.value if hasattr(label, "value") else str(label),
                "total_paise": int(total),
                "bill_count": int(count),
            }
            for label, total, count in result.tuples().all()
        ]

    async def get_store_totals(
        self, tenant_id: uuid.UUID, date_from: date, date_to: date
    ) -> list[StoreTotal]:
        range_start, range_end = _day_bounds(date_from)[0], _day_bounds(date_to)[1]
        revenue_col = func.coalesce(func.sum(Bill.total_paise), 0).label("total_paise")
        count_col = func.count(Bill.id).label("bill_count")

        # LEFT JOIN with the date/status filter in the ON clause (not WHERE)
        # so a store with zero bills in range still shows a 0 row instead of
        # disappearing entirely.
        stmt = (
            select(Store.id, Store.name, revenue_col, count_col)
            .select_from(Store)
            .outerjoin(
                Bill,
                and_(
                    Bill.store_id == Store.id,
                    Bill.status == BillStatus.COMPLETED,
                    Bill.created_at >= range_start,
                    Bill.created_at <= range_end,
                ),
            )
            .where(Store.tenant_id == tenant_id)
            .group_by(Store.id, Store.name)
            .order_by(Store.name)
        )
        result = await self.db.execute(stmt)
        return [
            {
                "store_id": store_id,
                "store_name": name,
                "total_paise": int(total),
                "bill_count": int(count),
            }
            for store_id, name, total, count in result.tuples().all()
        ]
