import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import DiscountScope, DiscountType


class DiscountRule(Base, UUIDPKMixin, TimestampMixin):
    """Item/category/bill discount rule (Pro+)."""

    __tablename__ = "discount_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[DiscountScope] = mapped_column(
        SAEnum(
            DiscountScope, name="discount_scope", values_callable=lambda x: [e.value for e in x]
        ),
        nullable=False,
    )
    # Polymorphic: item.id or category.id depending on scope, null when scope=bill.
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    type: Mapped[DiscountType] = mapped_column(
        "type",
        SAEnum(DiscountType, name="discount_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    # Integer per CLAUDE.md's no-float-money rule: for type=flat this is paise;
    # for type=percent this is basis points (10.50% -> 1050).
    value: Mapped[int] = mapped_column(BigInteger, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
