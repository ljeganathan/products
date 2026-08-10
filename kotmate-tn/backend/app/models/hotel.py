import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import INDIAN_STATES
from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column

_STATE_CHECK_SQL = "state IN ({})".format(", ".join(f"'{s}'" for s in INDIAN_STATES))
_PINCODE_CHECK_SQL = "pincode ~ '^[1-9][0-9]{5}$'"


class HotelMaster(UUIDPKMixin, TimestampMixin, Base):
    """One row per `tenant_location` — logo/GSTIN/UPI/Tamil-on-print toggle (CLAUDE.md §9/§10).
    `show_tamil_names` only controls the printed KOT/bill; the POS staff-facing grid always
    shows English+Tamil together regardless of this toggle.
    """

    __tablename__ = "hotel_master"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False, unique=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    door_no: Mapped[str | None] = mapped_column(String(50))
    street: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    pincode: Mapped[str | None] = mapped_column(String(6))
    phone: Mapped[str | None] = mapped_column(String(20))
    gstin: Mapped[str | None] = mapped_column(String(15))
    logo_url: Mapped[str | None] = mapped_column(String(500))
    upi_id: Mapped[str | None] = mapped_column(String(100))
    show_tamil_names: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Printed centered near the end of the bill (e.g. "Thank You & Visit Again..!!!"),
    # tenant-editable per location like the logo/GSTIN/UPI fields above. NULL means the
    # tenant hasn't set one — the print layer falls back to a generic default rather
    # than printing nothing, but doesn't hardcode that default here in the model.
    receipt_footer_message: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        tenant_composite_index("hotel_master"),
        CheckConstraint(_STATE_CHECK_SQL, name="ck_hotel_master_state_valid"),
        CheckConstraint(_PINCODE_CHECK_SQL, name="ck_hotel_master_pincode_format"),
        CheckConstraint(
            "gstin IS NULL OR gstin ~ '^[0-9]{2}[A-Z0-9]{13}$'", name="ck_hotel_master_gstin_format"
        ),
    )
