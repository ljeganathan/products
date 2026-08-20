"""order items line_no

Revision ID: a1c9e4d7b3f2
Revises: db07d0c0058e
Create Date: 2026-08-20 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1c9e4d7b3f2"
down_revision = "db07d0c0058e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills every existing order_items row to 0 in the same statement
    # (they all tie on line_no from then on, falling back to created_at/id ordering
    # exactly as before this column existed — a no-op for already-placed orders, never a
    # regression), then the default is dropped so every future insert must supply it
    # explicitly via the ORM (order_service.py's create_order/apply_line_changes) — same
    # two-step shape already used for every additive column in this codebase.
    op.add_column(
        "order_items",
        sa.Column("line_no", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("order_items", "line_no", server_default=None)


def downgrade() -> None:
    op.drop_column("order_items", "line_no")
