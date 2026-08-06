import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import BILLING_CYCLES, PAYMENT_STATUSES, PLAN_CODES, SUBSCRIPTION_STATUSES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Plan(UUIDPKMixin, TimestampMixin, Base):
    """Lite / Pro / Pro Max — CLAUDE.md §6/§7. Not tenant-scoped (platform table)."""

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # NULL = unlimited (Pro Max users, CLAUDE.md §6) — no magic-number sentinel.
    max_users: Mapped[int | None] = mapped_column(Integer)
    max_locations: Mapped[int] = mapped_column(Integer, nullable=False)
    price_monthly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price_yearly: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    # Remaining feature-matrix flags from CLAUDE.md §6 that aren't first-class enforced
    # columns (item_images, section_pricing, kot_printing, qr_upi, discount_types,
    # tax_mode, export_formats, kds, priority_support, ...) — editable by product_owner
    # (Phase 03) without a redeploy.
    features: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(f"code IN ({', '.join(repr(c) for c in PLAN_CODES)})", name="ck_plans_code_valid"),
    )


class Subscription(UUIDPKMixin, TimestampMixin, Base):
    """Assigns a tenant to a plan, tracks billing cycle + manual payment status (CLAUDE.md §7)."""

    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    plan_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")
    current_period_start: Mapped[date] = mapped_column(nullable=False)
    current_period_end: Mapped[date] = mapped_column(nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), nullable=False, default="paid")

    __table_args__ = (
        tenant_composite_index("subscriptions"),
        CheckConstraint(
            f"status IN ({', '.join(repr(c) for c in SUBSCRIPTION_STATUSES)})",
            name="ck_subscriptions_status_valid",
        ),
        CheckConstraint(
            f"billing_cycle IN ({', '.join(repr(c) for c in BILLING_CYCLES)})",
            name="ck_subscriptions_billing_cycle_valid",
        ),
        CheckConstraint(
            f"payment_status IN ({', '.join(repr(c) for c in PAYMENT_STATUSES)})",
            name="ck_subscriptions_payment_status_valid",
        ),
    )
