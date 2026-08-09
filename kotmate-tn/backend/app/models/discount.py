import uuid
from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import DISCOUNT_MODES, DISCOUNT_TYPES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class DiscountRule(UUIDPKMixin, TimestampMixin, Base):
    """flat_percent (all tiers), item_level (Pro+), coupon (Pro Max) — CLAUDE.md §6.
    Rules auto-apply at billing time (bill_service._compute_discount) rather than being
    chosen manually per bill — `is_active` + `expires_at` together gate eligibility.
    """

    __tablename__ = "discount_rules"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    # percent: value is 0-100, applied as a % off the base. rupee: value is a flat ₹
    # amount off the base (capped to the base itself by the billing calculation).
    discount_mode: Mapped[str] = mapped_column(String(10), nullable=False, default="percent")
    value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    # Only set for type="item_level" — the specific item this rule discounts.
    item_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("items.id"))
    coupon_code: Mapped[str | None] = mapped_column(String(30))
    expires_at: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("discount_rules"),
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in DISCOUNT_TYPES)})", name="ck_discount_rules_type_valid"
        ),
        CheckConstraint(
            f"discount_mode IN ({', '.join(repr(m) for m in DISCOUNT_MODES)})",
            name="ck_discount_rules_mode_valid",
        ),
        Index(
            "uq_discount_rules_tenant_id_coupon_code",
            "tenant_id",
            "coupon_code",
            unique=True,
            postgresql_where=text("coupon_code IS NOT NULL"),
        ),
    )
