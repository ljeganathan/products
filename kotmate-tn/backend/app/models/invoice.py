import uuid
from datetime import date

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import INVOICE_STATUSES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Invoice(UUIDPKMixin, TimestampMixin, Base):
    """Tenant subscription billing document (CLAUDE.md §8, Phase 14) — a platform-owner
    tool for invoicing a tenant's subscription fee, distinct from the POS `bills` table
    (which bills a tenant's own customers). Single flat `amount` per invoice, matching
    `plans.price_monthly`/`price_yearly` being flat-priced — no line-item breakdown.
    """

    __tablename__ = "invoices"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("subscriptions.id"), nullable=True
    )
    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    issued_date: Mapped[date] = mapped_column(nullable=False)
    due_date: Mapped[date] = mapped_column(nullable=False)
    paid_date: Mapped[date | None] = mapped_column(nullable=True)
    description: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        tenant_composite_index("invoices"),
        CheckConstraint(
            f"status IN ({', '.join(repr(c) for c in INVOICE_STATUSES)})",
            name="ck_invoices_status_valid",
        ),
    )
