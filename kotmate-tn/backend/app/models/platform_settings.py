from sqlalchemy import Boolean, CheckConstraint, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class PlatformSettings(TimestampMixin, Base):
    """Singleton row (Phase 03) — maintenance-mode toggle + announcement banner, the
    only platform-wide mutable settings that aren't per-tenant. Not tenant-scoped, no
    UUID PK mixin: `id` is pinned to 1 by a CHECK constraint so there is always exactly
    one row, seeded by this table's own migration.
    """

    __tablename__ = "platform_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    maintenance_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    maintenance_message: Mapped[str | None] = mapped_column(Text)
    announcement_is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    announcement_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (CheckConstraint("id = 1", name="ck_platform_settings_singleton"),)
