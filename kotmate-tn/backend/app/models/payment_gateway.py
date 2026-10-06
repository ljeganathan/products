import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class TenantPaymentGateway(UUIDPKMixin, TimestampMixin, Base):
    """One row per (tenant, provider): that hotel's credentials for each online payment
    provider (Phase 28 Razorpay, Cashfree later). Secrets are stored encrypted
    (`app/core/secrets.py`) and never returned by any API. At most one row per tenant is
    enabled at a time, enforced by the partial unique index below.

    `auth_mode` keeps the Razorpay credential model swappable without a schema change:
    'api_keys' (the hotel's own key id + secret); a future Razorpay Partner integration
    would use 'partner_oauth', storing the sub-merchant's access token in
    `secret_encrypted` and its account id in `account_ref`. `environment` is Cashfree's
    explicit 'sandbox' | 'production' switch (NULL for Razorpay, which reads it from the
    key prefix). Only `services/payment_gateway.py` interprets these columns.
    """

    __tablename__ = "tenant_payment_gateways"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="razorpay")
    auth_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="api_keys")
    key_id: Mapped[str | None] = mapped_column(String(100))
    secret_encrypted: Mapped[str | None] = mapped_column(Text)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    account_ref: Mapped[str | None] = mapped_column(String(100))
    environment: Mapped[str | None] = mapped_column(String(10))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        tenant_composite_index("tenant_payment_gateways"),
        UniqueConstraint("tenant_id", "provider", name="uq_tenant_payment_gateways_tenant_provider"),
        Index(
            "uq_tenant_payment_gateways_one_enabled",
            "tenant_id",
            unique=True,
            postgresql_where=text("is_enabled"),
        ),
        CheckConstraint("provider IN ('razorpay', 'cashfree')", name="ck_tenant_pg_provider_valid"),
    )


class PaymentAttempt(UUIDPKMixin, TimestampMixin, Base):
    """One gateway order created for a guest's bill. The gateway (not the customer's
    browser) is the source of truth for whether it was paid — `status` only moves to
    'paid' after the backend confirmed it with the gateway or a signed webhook.
    """

    __tablename__ = "payment_attempts"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    order_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("guest_sessions.id")
    )
    bill_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id"))
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_order_id: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(String(64))
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="created")
    method: Mapped[str | None] = mapped_column(String(20))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        tenant_composite_index("payment_attempts"),
        Index("ix_payment_attempts_tenant_order", "tenant_id", "order_id"),
        UniqueConstraint("provider", "provider_order_id", name="uq_payment_attempts_provider_order"),
        CheckConstraint("status IN ('created', 'paid', 'failed')", name="ck_payment_attempts_status_valid"),
    )
