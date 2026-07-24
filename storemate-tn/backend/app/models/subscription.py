import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import InvoiceStatus, SubscriptionStatus


class Subscription(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        SAEnum(
            SubscriptionStatus,
            name="subscription_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
    )
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extra_users: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extra_stores: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Nullable: not assigned until the gateway subscription is actually created.
    razorpay_subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Tenant-side "Upgrade" flow (Phase 7, manual-payment v1): an admin can
    # request a plan change without a code deploy or gateway integration; the
    # product owner console surfaces it and resolves it via change-plan
    # (which clears both fields below) — see api/v1/subscription.py.
    requested_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    upgrade_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SubscriptionInvoice(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "subscription_invoices"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    gst_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[InvoiceStatus] = mapped_column(
        SAEnum(
            InvoiceStatus, name="invoice_status", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
        default=InvoiceStatus.PENDING,
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
