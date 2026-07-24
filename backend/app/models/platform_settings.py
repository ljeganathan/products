from sqlalchemy import Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin


class PlatformSettings(Base, UUIDPKMixin, TimestampMixin):
    """Singleton row (product_owner scope) — the repository always reads/
    creates the first row rather than looking up by a fixed id."""

    __tablename__ = "platform_settings"

    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maintenance_message: Mapped[str | None] = mapped_column(Text, nullable=True)
