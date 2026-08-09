import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column

_REASONS = ("manual_set", "kot_deduction", "restock")


class StockLedger(UUIDPKMixin, TimestampMixin, Base):
    """Audit trail for every `items.available_qty` change (extends the Phase 05/08 soft-
    inventory feature). `change_qty` is signed — negative for the KOT-send deduction,
    positive/any for a manual set or restock. `location_id` is nullable because items
    themselves are tenant-wide, not per-location (CLAUDE.md §8) — only populated for
    `kot_deduction` rows, where the triggering order's location is meaningful.
    `reference_order_id` (not `reference_bill_id`) is what's populated for
    `kot_deduction`, since deduction fires at KOT-send, before any bill exists;
    `reference_bill_id` is kept for schema completeness but unused in this phase.
    """

    __tablename__ = "stock_ledger"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    item_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id")
    )
    change_qty: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    reference_order_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("orders.id"))
    reference_bill_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id"))

    __table_args__ = (
        tenant_composite_index("stock_ledger"),
        CheckConstraint(
            f"reason IN ({', '.join(repr(r) for r in _REASONS)})", name="ck_stock_ledger_reason_valid"
        ),
    )
