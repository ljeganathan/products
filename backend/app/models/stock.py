import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import StockMovementReason


class Stock(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "stock"
    __table_args__ = (
        Index("ix_stock_tenant_store_item", "tenant_id", "store_id", "item_id", unique=True),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Numeric, not Integer: FMCG units include kg/g/l/ml which are commonly fractional.
    quantity_on_hand: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    last_restocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class StockMovement(Base, UUIDPKMixin, TimestampMixin):
    """Append-only audit trail of every +/- change to stock quantity."""

    __tablename__ = "stock_movements"
    __table_args__ = (
        Index("ix_stock_movements_tenant_item_created", "tenant_id", "item_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_qty: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[StockMovementReason] = mapped_column(
        SAEnum(
            StockMovementReason,
            name="stock_movement_reason",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    # Polymorphic: references a bills.id or a purchase-order id — no FK constraint.
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
