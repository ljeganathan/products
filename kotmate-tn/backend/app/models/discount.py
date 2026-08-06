import uuid

from sqlalchemy import Boolean, CheckConstraint, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import DISCOUNT_TYPES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class DiscountRule(UUIDPKMixin, TimestampMixin, Base):
    """flat_percent (all tiers), item_level (Pro+), coupon (Pro Max) — CLAUDE.md §6."""

    __tablename__ = "discount_rules"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(10, 2))
    coupon_code: Mapped[str | None] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("discount_rules"),
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in DISCOUNT_TYPES)})", name="ck_discount_rules_type_valid"
        ),
        Index(
            "uq_discount_rules_tenant_id_coupon_code",
            "tenant_id",
            "coupon_code",
            unique=True,
            postgresql_where=text("coupon_code IS NOT NULL"),
        ),
    )
