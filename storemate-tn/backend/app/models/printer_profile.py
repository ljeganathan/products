import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import PrinterConnection, PrinterType


class PrinterProfile(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "printer_profiles"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[PrinterType] = mapped_column(
        "type",
        SAEnum(PrinterType, name="printer_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    connection: Mapped[PrinterConnection] = mapped_column(
        SAEnum(
            PrinterConnection,
            name="printer_connection",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paper_width_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    # Connection-specific fields — deliberately unstructured JSON since each
    # connection type needs a different shape (network: {ip, port};
    # bluetooth: {bluetooth_device_id, bluetooth_device_name}) and this only
    # ever feeds the frontend print dispatcher / network transport, never
    # gets queried on.
    connection_details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
