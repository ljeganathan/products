import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column


class Waiter(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "waiters"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )
    waiter_number: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    # % rate on net sale value (post-discount, pre-tax) — CLAUDE.md §11.
    incentive_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    # Optional link to a `waiter`-role login (Phase 04 `users`) — when set, the POS
    # screen (Phase 07) auto-locks that login's waiter selector to this row so every
    # order they build is self-attributed with no extra step (CLAUDE.md §11). A Waiter
    # Master row doesn't require a login (some tenants track waiters without giving them
    # app access), so this stays nullable rather than merging the two entities.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("waiters"),
        Index(
            "uq_waiters_tenant_id_location_id_waiter_number",
            "tenant_id",
            "location_id",
            "waiter_number",
            unique=True,
        ),
    )
