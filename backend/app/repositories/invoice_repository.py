import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import InvoiceStatus
from app.models.subscription import SubscriptionInvoice
from app.models.tenant import Tenant


class InvoiceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def _joined_query(self):  # noqa: ANN202
        return select(SubscriptionInvoice, Tenant).join(
            Tenant, Tenant.id == SubscriptionInvoice.tenant_id
        )

    async def get_by_id_joined(
        self, invoice_id: uuid.UUID
    ) -> tuple[SubscriptionInvoice, Tenant] | None:
        result = await self.db.execute(
            self._joined_query().where(SubscriptionInvoice.id == invoice_id)
        )
        row = result.first()
        if row is None:
            return None
        invoice, tenant = row
        return invoice, tenant

    async def count_by_invoice_number_prefix(self, prefix: str) -> int:
        return (
            await self.db.scalar(
                select(func.count())
                .select_from(SubscriptionInvoice)
                .where(SubscriptionInvoice.invoice_number.like(f"{prefix}%"))
            )
            or 0
        )

    async def list_all(
        self,
        *,
        page: int,
        page_size: int,
        tenant_id: uuid.UUID | None = None,
        status: InvoiceStatus | None = None,
    ) -> tuple[list[tuple[SubscriptionInvoice, Tenant]], int]:
        query = self._joined_query()
        if tenant_id is not None:
            query = query.where(SubscriptionInvoice.tenant_id == tenant_id)
        if status is not None:
            query = query.where(SubscriptionInvoice.status == status)

        total = await self.db.scalar(select(func.count()).select_from(query.subquery()))
        result = await self.db.execute(
            query.order_by(SubscriptionInvoice.issued_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = [(invoice, tenant) for invoice, tenant in result.all()]
        return rows, total or 0

    async def create(self, invoice: SubscriptionInvoice) -> SubscriptionInvoice:
        self.db.add(invoice)
        await self.db.flush()
        return invoice
