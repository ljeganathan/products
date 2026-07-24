from sqlalchemy import Enum as SAEnum
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import TenantStatus


class Tenant(Base, UUIDPKMixin, TimestampMixin):
    """A subscribing store business (product_owner scope)."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    owner_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        SAEnum(TenantStatus, name="tenant_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TenantStatus.TRIAL,
    )
