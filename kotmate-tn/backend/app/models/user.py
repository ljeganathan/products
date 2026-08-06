import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin, tenant_composite_index, tenant_id_column

_USER_ID_CHECK_SQL = "user_id ~ '^[A-Za-z0-9_-]{2,60}$'"


class Role(UUIDPKMixin, TimestampMixin, Base):
    """Shared lookup table — not tenant-scoped. product_owner/tenant_admin/pos_user/waiter/kitchen."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class User(UUIDPKMixin, TimestampMixin, Base):
    """Login is always by `user_id` — never email (CLAUDE.md §5). `tenant_id` is nullable
    only for `product_owner`.

    `user_id` is the literal login value and is globally unique across the whole
    platform (a single unique constraint, no per-tenant partial index): for
    tenant-scoped roles it is composed at creation time (Phase 04) as
    `{tenant.tenant_code}-{local_handle}` so two tenants can each use a plain local
    handle like "admin01" without colliding, while product_owner rows use a bare,
    admin-chosen `user_id` with no prefix.
    """

    __tablename__ = "users"

    tenant_id: Mapped[uuid.UUID | None] = tenant_id_column(nullable=True)
    user_id: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    # % rate on net sale value (post-discount, pre-tax); only meaningful when role=pos_user (cashier).
    incentive_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        tenant_composite_index("users"),
        CheckConstraint(_USER_ID_CHECK_SQL, name="ck_users_user_id_format"),
    )


class UserLocationAccess(UUIDPKMixin, TimestampMixin, Base):
    """Per-location access grants — relevant now that every tier can have multiple
    locations (CLAUDE.md §4), not just Pro Max.
    """

    __tablename__ = "user_location_access"

    tenant_id: Mapped[uuid.UUID] = tenant_id_column()
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    location_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenant_locations.id"), nullable=False
    )

    __table_args__ = (
        tenant_composite_index("user_location_access"),
        Index("uq_user_location_access_user_id_location_id", "user_id", "location_id", unique=True),
    )
