import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPKMixin
from app.models.enums import LanguagePref, UserRole


class User(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "users"

    # Nullable: product_owner accounts are platform-level and belong to no tenant.
    # This extends docs/DATABASE_SCHEMA.md's users.role (admin|pos_user) with
    # product_owner — see the "Deviations" note at the top of that doc.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    store_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    language_pref: Mapped[LanguagePref] = mapped_column(
        SAEnum(LanguagePref, name="language_pref", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=LanguagePref.EN,
    )
    # Phase 9 login lockout (services/auth_service.py). DB-backed rather than
    # in-memory/Redis: production runs multiple gunicorn worker processes
    # (docker-compose.prod.yml), so an in-process counter wouldn't see
    # attempts routed to a different worker — the `users` row is the one
    # place every worker agrees on.
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
