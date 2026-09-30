"""marketing content: blog posts and demo videos (platform-wide, not tenant-scoped)

Revision ID: f1a3c8e2b567
Revises: e5b2c7d91a34
Create Date: 2026-09-30 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "f1a3c8e2b567"
down_revision = "e5b2c7d91a34"
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # Platform-wide content (the landing site's public "Demos & Blog" page, Phase 29) —
    # same "not tenant-scoped, no RLS" precedent as `plans`/`roles`: there is no tenant_id
    # to isolate by, and access is controlled entirely at the API layer (writes require
    # product_owner via the existing /platform router gate; reads are public but only ever
    # return is_published=true rows). Two brand-new tables — no existing data touched.
    op.create_table(
        "marketing_blog_posts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column("excerpt", sa.String(300), nullable=True),
        sa.Column("body_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_marketing_blog_posts_slug"),
    )
    op.create_index(
        "ix_marketing_blog_posts_published", "marketing_blog_posts", ["is_published", "published_at"]
    )

    op.create_table(
        "marketing_demo_videos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        # A YouTube/Vimeo watch URL, not a self-hosted file — see docs/MARKETING_CONTENT.md.
        sa.Column("video_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marketing_demo_videos_published", "marketing_demo_videos", ["is_published", "display_order"]
    )


def downgrade() -> None:
    op.drop_index("ix_marketing_demo_videos_published", table_name="marketing_demo_videos")
    op.drop_table("marketing_demo_videos")
    op.drop_index("ix_marketing_blog_posts_published", table_name="marketing_blog_posts")
    op.drop_table("marketing_blog_posts")
