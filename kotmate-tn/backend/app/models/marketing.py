from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UUIDPKMixin


class BlogPost(UUIDPKMixin, TimestampMixin, Base):
    """Landing-site "Demos & Blog" page content (Phase 29). Not tenant-scoped — same
    platform-wide, no-RLS precedent as `Plan`/`Role`: there's no tenant to isolate by,
    and access is controlled at the API layer (writes are product_owner-only via the
    `/platform` router gate; the public read endpoint only ever returns published rows).
    """

    __tablename__ = "marketing_blog_posts"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    cover_image_url: Mapped[str | None] = mapped_column(Text)
    excerpt: Mapped[str | None] = mapped_column(String(300))
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_marketing_blog_posts_published", "is_published", "published_at"),)


class DemoVideo(UUIDPKMixin, TimestampMixin, Base):
    """A YouTube/Vimeo link, not a self-hosted file — see docs/MARKETING_CONTENT.md for
    why (storage/bandwidth cost and streaming complexity aren't worth it for this).
    """

    __tablename__ = "marketing_demo_videos"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    video_url: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(300))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (Index("ix_marketing_demo_videos_published", "is_published", "display_order"),)
