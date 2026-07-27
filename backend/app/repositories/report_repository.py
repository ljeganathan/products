import uuid
from datetime import date, datetime
from typing import Any, TypedDict

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill, BillItem
from app.models.enums import BillStatus, PaymentMode
from app.models.item import Item
from app.models.user import User


class DailyPoint(TypedDict):
    bucket: datetime
    total_paise: int
    bill_count: int


class SalesReport(TypedDict):
    total_paise: int
    bill_count: int
    avg_bill_paise: int
    profit_paise: int
    daily: list[DailyPoint]


class GstSummary(TypedDict):
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    total_paise: int
    bill_count: int


class SalesCsvRow(TypedDict):
    bill_number: int
    created_at: datetime
    cashier_name: str
    customer_name: str | None
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    round_off_paise: int
    total_paise: int
    payment_mode: PaymentMode


def _range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(date_from, datetime.min.time()),
        datetime.combine(date_to, datetime.max.time()),
    )


class ReportRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _base_filters(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        cashier_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
    ) -> list[Any]:
        range_start, range_end = _range_bounds(date_from, date_to)
        filters = [
            Bill.tenant_id == tenant_id,
            Bill.status == BillStatus.COMPLETED,
            Bill.created_at >= range_start,
            Bill.created_at <= range_end,
        ]
        if store_id is not None:
            filters.append(Bill.store_id == store_id)
        if cashier_id is not None:
            filters.append(Bill.cashier_id == cashier_id)
        return filters

    async def get_sales_report(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        cashier_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
    ) -> SalesReport:
        filters = self._base_filters(tenant_id, store_id, cashier_id, date_from, date_to)

        total_paise, bill_count = (
            await self.db.execute(
                select(func.coalesce(func.sum(Bill.total_paise), 0), func.count()).where(*filters)
            )
        ).one()

        bucket_col = func.date_trunc("day", Bill.created_at).label("bucket")
        revenue_col = func.sum(Bill.total_paise).label("total_paise")
        count_col = func.count(Bill.id).label("bill_count")
        daily_result = await self.db.execute(
            select(bucket_col, revenue_col, count_col)
            .where(*filters)
            .group_by(bucket_col)
            .order_by(bucket_col)
        )
        daily: list[DailyPoint] = [
            {"bucket": bucket, "total_paise": int(total), "bill_count": int(count)}
            for bucket, total, count in daily_result.tuples().all()
        ]

        profit_paise = await self._get_profit_paise(
            tenant_id, store_id, cashier_id, date_from, date_to
        )

        return {
            "total_paise": int(total_paise),
            "bill_count": int(bill_count),
            "avg_bill_paise": round(total_paise / bill_count) if bill_count else 0,
            "profit_paise": profit_paise,
            "daily": daily,
        }

    async def _get_profit_paise(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        cashier_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
    ) -> int:
        """Profit = per-line revenue net of discount (pre-tax) minus cost,
        using each item's *current* cost_price_paise — bill_items has no
        cost snapshot at sale time, so this is an approximation that shifts
        if an item's cost is edited after past sales."""
        filters = self._base_filters(tenant_id, store_id, cashier_id, date_from, date_to)
        revenue_expr = (
            func.round(BillItem.qty * BillItem.unit_price_paise) - BillItem.discount_paise
        )
        cost_expr = func.round(BillItem.qty * Item.cost_price_paise)
        profit_paise = await self.db.scalar(
            select(func.coalesce(func.sum(revenue_expr - cost_expr), 0))
            .select_from(BillItem)
            .join(Bill, Bill.id == BillItem.bill_id)
            .join(Item, Item.id == BillItem.item_id)
            .where(*filters)
        )
        return int(profit_paise)

    async def get_gst_summary(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        cashier_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
    ) -> GstSummary:
        filters = self._base_filters(tenant_id, store_id, cashier_id, date_from, date_to)
        row = (
            await self.db.execute(
                select(
                    func.coalesce(func.sum(Bill.subtotal_paise), 0),
                    func.coalesce(func.sum(Bill.discount_paise), 0),
                    func.coalesce(func.sum(Bill.cgst_paise), 0),
                    func.coalesce(func.sum(Bill.sgst_paise), 0),
                    func.coalesce(func.sum(Bill.total_paise), 0),
                    func.count(),
                ).where(*filters)
            )
        ).one()
        subtotal, discount, cgst, sgst, total, count = row
        return {
            "subtotal_paise": int(subtotal),
            "discount_paise": int(discount),
            "cgst_paise": int(cgst),
            "sgst_paise": int(sgst),
            "total_paise": int(total),
            "bill_count": int(count),
        }

    async def list_sales_rows_for_csv(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        cashier_id: uuid.UUID | None,
        date_from: date,
        date_to: date,
    ) -> list[SalesCsvRow]:
        filters = self._base_filters(tenant_id, store_id, cashier_id, date_from, date_to)
        result = await self.db.execute(
            select(
                Bill.bill_number,
                Bill.created_at,
                User.name,
                Bill.customer_name,
                Bill.subtotal_paise,
                Bill.discount_paise,
                Bill.cgst_paise,
                Bill.sgst_paise,
                Bill.round_off_paise,
                Bill.total_paise,
                Bill.payment_mode,
            )
            .join(User, User.id == Bill.cashier_id)
            .where(*filters)
            .order_by(Bill.created_at)
        )
        return [
            {
                "bill_number": bill_number,
                "created_at": created_at,
                "cashier_name": cashier_name,
                "customer_name": customer_name,
                "subtotal_paise": subtotal_paise,
                "discount_paise": discount_paise,
                "cgst_paise": cgst_paise,
                "sgst_paise": sgst_paise,
                "round_off_paise": round_off_paise,
                "total_paise": total_paise,
                "payment_mode": payment_mode,
            }
            for (
                bill_number,
                created_at,
                cashier_name,
                customer_name,
                subtotal_paise,
                discount_paise,
                cgst_paise,
                sgst_paise,
                round_off_paise,
                total_paise,
                payment_mode,
            ) in result.tuples().all()
        ]
