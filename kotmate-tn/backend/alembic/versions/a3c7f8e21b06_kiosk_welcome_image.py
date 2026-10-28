"""Kiosk idle-screen welcome image (per hotel_master row/location).

Revision ID: a3c7f8e21b06
Revises: d2f6b8a1c4e9
Create Date: 2026-10-28 00:00:00.000000

Production-safe by construction: one new nullable column, no backfill needed (NULL
means "no custom image uploaded yet", which the kiosk idle screen already falls back
to a built-in default design for).
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a3c7f8e21b06"
down_revision: Union[str, None] = "d2f6b8a1c4e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotel_master", sa.Column("kiosk_welcome_image_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("hotel_master", "kiosk_welcome_image_url")
