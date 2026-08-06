import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import KOT_TICKET_STATUSES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class KotTicket(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "kot_tickets"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    order_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="new")

    __table_args__ = (
        tenant_composite_index("kot_tickets"),
        Index("uq_kot_tickets_tenant_id_ticket_number", "tenant_id", "ticket_number", unique=True),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in KOT_TICKET_STATUSES)})",
            name="ck_kot_tickets_status_valid",
        ),
    )


class KotTicketItem(UUIDPKMixin, TimestampMixin, Base):
    """Links a KOT ticket to the specific order_items it fired — supports repeat-KOT for
    add-on items ordered after the first ticket (Phase 08).
    """

    __tablename__ = "kot_ticket_items"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    kot_ticket_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("kot_tickets.id"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("order_items.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (tenant_composite_index("kot_ticket_items"),)
