"""Kitchen tickets record which screen claimed them for browser printing.

Revision ID: e1a5c9d3b7f2
Revises: d8f2b6a4c1e9
Create Date: 2026-10-07 09:00:00.000000

Production-safe: adds one nullable column with no default and no backfill. Existing tickets
stay NULL (unclaimed), and nothing reprints them: a screen only prints tickets that appear
after it opens.
"""

import sqlalchemy as sa

from alembic import op

revision = "e1a5c9d3b7f2"
down_revision = "d8f2b6a4c1e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kot_tickets", sa.Column("print_claimed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("kot_tickets", "print_claimed_at")
