import uuid
from datetime import date, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bill import Bill, BillItem
from app.models.enums import BillStatus


class BillRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def next_bill_number(self, tenant_id: uuid.UUID, store_id: uuid.UUID) -> int:
        """Sequential per store. No dedicated counter table in the schema, so
        this computes MAX+1; the caller retries on a unique-constraint
        collision (see billing_service.create_bill) to stay correct under
        the rare concurrent-checkout race."""
        current_max = await self.db.scalar(
            select(func.max(Bill.bill_number)).where(
                Bill.tenant_id == tenant_id, Bill.store_id == store_id
            )
        )
        return (current_max or 0) + 1

    async def create(self, bill: Bill) -> Bill:
        self.db.add(bill)
        await self.db.flush()
        return bill

    async def add_items(self, items: list[BillItem]) -> None:
        self.db.add_all(items)
        await self.db.flush()

    async def get_by_id_for_tenant(
        self, bill_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Bill | None:
        return await self.db.scalar(
            select(Bill).where(Bill.id == bill_id, Bill.tenant_id == tenant_id)
        )

    async def get_items(self, bill_id: uuid.UUID) -> list[BillItem]:
        result = await self.db.execute(select(BillItem).where(BillItem.bill_id == bill_id))
        return list(result.scalars().all())

    async def delete_with_items(self, bill: Bill) -> None:
        await self.db.execute(delete(BillItem).where(BillItem.bill_id == bill.id))
        await self.db.delete(bill)
        await self.db.flush()

    async def list_held_for_cashier(
        self, tenant_id: uuid.UUID, store_id: uuid.UUID, cashier_id: uuid.UUID
    ) -> list[Bill]:
        result = await self.db.execute(
            select(Bill)
            .where(
                Bill.tenant_id == tenant_id,
                Bill.store_id == store_id,
                Bill.cashier_id == cashier_id,
                Bill.status == BillStatus.HELD,
            )
            .order_by(Bill.created_at.desc())
        )
        return list(result.scalars().all())

    async def search(
        self,
        tenant_id: uuid.UUID,
        store_id: uuid.UUID | None,
        *,
        page: int,
        page_size: int,
        bill_number: int | None,
        date_from: date | None,
        date_to: date | None,
        cashier_id: uuid.UUID | None,
        customer_phone: str | None,
        status: BillStatus | None,
    ) -> tuple[list[Bill], int]:
        stmt = select(Bill).where(Bill.tenant_id == tenant_id)
        count_stmt = select(func.count()).select_from(Bill).where(Bill.tenant_id == tenant_id)

        filters = []
        if store_id is not None:
            filters.append(Bill.store_id == store_id)
        if bill_number is not None:
            filters.append(Bill.bill_number == bill_number)
        if date_from is not None:
            filters.append(Bill.created_at >= datetime.combine(date_from, datetime.min.time()))
        if date_to is not None:
            filters.append(Bill.created_at <= datetime.combine(date_to, datetime.max.time()))
        if cashier_id is not None:
            filters.append(Bill.cashier_id == cashier_id)
        if customer_phone:
            filters.append(Bill.customer_phone == customer_phone)
        if status is not None:
            filters.append(Bill.status == status)

        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

        total = await self.db.scalar(count_stmt) or 0
        stmt = stmt.order_by(Bill.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total
