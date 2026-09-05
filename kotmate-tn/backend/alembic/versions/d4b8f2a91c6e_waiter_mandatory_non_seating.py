"""add waiter-mandatory-for-non-seating tenant toggle

Revision ID: d4b8f2a91c6e
Revises: c8a3e6f10b57
Create Date: 2026-09-05 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d4b8f2a91c6e"
down_revision = "c8a3e6f10b57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Additive-only — every existing tenant row backfills to False, matching today's
    # actual behavior (non-seating orders never require a waiter regardless of the
    # existing waiter_mandatory_enabled toggle), so no tenant's POS experience changes
    # on deploy. Same two-step server_default pattern already used for every other
    # tenant-wide preference toggle in this table.
    op.add_column(
        "tenants",
        sa.Column(
            "waiter_mandatory_non_seating_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("tenants", "waiter_mandatory_non_seating_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "waiter_mandatory_non_seating_enabled")
