import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ORDER_STATUSES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Order(UUIDPKMixin, TimestampMixin, Base):
    """The server-persisted "cart" (CLAUDE.md §11) — `open -> held -> billed`.
    `table_id` is nullable (null for non-seating sections like Takeaway/Online Delivery);
    `section_id` is always set since it drives item price resolution (Phase 07).
    """

    __tablename__ = "orders"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    table_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("tables.id"))
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id"), nullable=False
    )
    waiter_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("waiters.id"))
    # Cashier-of-record — whichever pos_user is logged in and rang up the order (CLAUDE.md §11).
    pos_user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    hold_label: Mapped[str | None] = mapped_column(String(100))

    __table_args__ = (
        tenant_composite_index("orders"),
        Index("ix_orders_tenant_id_status", "tenant_id", "status"),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in ORDER_STATUSES)})", name="ck_orders_status_valid"
        ),
    )


class OrderItem(UUIDPKMixin, TimestampMixin, Base):
    """`unit_price` is snapshotted at add-time from the section-resolved price so later
    item/section-price master edits never retroactively change an open/held order (Phase 07).
    """

    __tablename__ = "order_items"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    order_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    item_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("items.id"), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    notes: Mapped[str | None] = mapped_column(String(300))
    is_kot_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        tenant_composite_index("order_items"),
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
    )
