import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class TableQrCode(UUIDPKMixin, TimestampMixin, Base):
    """One row per TABLE (Phase 25 — production feedback: a separate physical QR per
    seat is not something a restaurant can realistically print/laminate/replace).
    Whoever scans it shares the table's one active guest order — there's no
    customer-number concept to resolve. `qr_token` never rotates once printed; a
    torn/reprinted QR is the reset path.
    """

    __tablename__ = "table_qr_codes"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    table_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("tables.id"), nullable=False)
    qr_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("table_qr_codes"),
        UniqueConstraint("table_id", name="uq_table_qr_codes_table"),
    )


class GuestSession(UUIDPKMixin, TimestampMixin, Base):
    """A table's one shared, active QR-ordering session — everyone who scans that
    table's single QR joins this same order. No party_label/seat-splitting concept
    here at all (that stays a separate, staff-side-only feature, CLAUDE.md §11's
    CustomerSelectorBar) — a QR self-order table always orders and bills as one party.

    A Takeaway/non-seating session (Phase 26) is the opposite: `table_id` is null,
    `section_id` is set instead, and — unlike a table — it is NEVER shared or resumed
    across scans; every scan of the section's one QR starts a brand-new, independent
    order with its own `pickup_token` (e.g. "TA-14"), since two strangers scanning a
    counter's Takeaway code are two unrelated customers, not one shared cart. Resolved
    by `guest_session_id` (the JWT subject) directly rather than by table/section
    lookup — see `core/deps.py`'s `CurrentGuest`.
    """

    __tablename__ = "guest_sessions"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    table_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("tables.id"))
    section_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id")
    )
    pickup_token: Mapped[str | None] = mapped_column(String(20))
    customer_name: Mapped[str | None] = mapped_column(String(100))
    customer_phone: Mapped[str | None] = mapped_column(String(20))
    order_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), ForeignKey("orders.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        tenant_composite_index("guest_sessions"),
        CheckConstraint(
            "status IN ('active', 'payment_claimed', 'closed')", name="ck_guest_sessions_status_valid"
        ),
        CheckConstraint(
            "table_id IS NOT NULL OR section_id IS NOT NULL", name="ck_guest_sessions_table_or_section"
        ),
        # At most one *active* session per table — any scan of that table's one QR
        # either joins this row or (once closed by a staff bill finalize) starts the
        # next one. Postgres treats every NULL as distinct in a unique index, so this
        # naturally allows unlimited simultaneous Takeaway (table_id IS NULL) rows —
        # deliberate, since those are never "at most one," they're never shared at all.
        Index(
            "uq_guest_sessions_active_table",
            "tenant_id",
            "table_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class SectionQrCode(UUIDPKMixin, TimestampMixin, Base):
    """One row per (location, non-seating SECTION) — e.g. Takeaway, Online Delivery —
    the Phase 26 counterpart to `TableQrCode`. Keyed on the (location, section) pair
    rather than the section alone: `seating_sections` is tenant-wide, not per-location
    (a multi-location tenant's "Takeaway" section is one shared row used by every
    branch), so each branch still needs — and gets — its own separate QR/pickup-token
    sequence. Printed once at the counter; whoever scans it starts their own
    independent order, never a shared one (see `GuestSession`'s docstring).
    """

    __tablename__ = "section_qr_codes"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    section_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("seating_sections.id"), nullable=False
    )
    qr_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("section_qr_codes"),
        UniqueConstraint("location_id", "section_id", name="uq_section_qr_codes_location_section"),
    )
