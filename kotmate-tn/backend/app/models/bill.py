import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import BILL_STATUSES, PAYMENT_METHODS
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Bill(UUIDPKMixin, TimestampMixin, Base):
    """A finalized order (Phase 09). `table_id`/`section_id`/waiter/cashier are snapshotted
    at bill time (not just referenced) so reprints stay correct even if the table/waiter
    master data changes later. CGST/SGST are always two distinct amount columns
    (CLAUDE.md §9) and `round_off_amount` is the explicit, signed rounding delta shown on
    print rather than silently absorbed.
    """

    __tablename__ = "bills"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False, unique=True
    )
    bill_number: Mapped[str] = mapped_column(String(30), nullable=False)
    table_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("tables.id"))
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id"), nullable=False
    )
    waiter_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("waiters.id"))
    pos_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    cgst_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    sgst_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    round_off_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    waiter_incentive_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    cashier_incentive_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="finalized")

    __table_args__ = (
        tenant_composite_index("bills"),
        Index("uq_bills_tenant_id_bill_number", "tenant_id", "bill_number", unique=True),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in BILL_STATUSES)})", name="ck_bills_status_valid"
        ),
    )


class BillItem(UUIDPKMixin, TimestampMixin, Base):
    """Name is snapshotted (`name_en_snapshot`/`name_ta_snapshot`) since item master data
    can be renamed later but a finalized bill must stay immutable.
    """

    __tablename__ = "bill_items"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    bill_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    name_en_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    name_ta_snapshot: Mapped[str | None] = mapped_column(String(150))
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (tenant_composite_index("bill_items"),)


class Payment(UUIDPKMixin, TimestampMixin, Base):
    """Split payment lines — CLAUDE.md §9 orders methods UPI, then Cash, then Card."""

    __tablename__ = "payments"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    bill_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("bills.id"), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    __table_args__ = (
        tenant_composite_index("payments"),
        CheckConstraint(
            f"method IN ({', '.join(repr(m) for m in PAYMENT_METHODS)})", name="ck_payments_method_valid"
        ),
    )
