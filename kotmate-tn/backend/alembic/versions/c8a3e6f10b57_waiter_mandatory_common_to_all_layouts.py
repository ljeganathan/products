"""rename guided-pos-only waiter mandatory toggle to a layout-agnostic one

Revision ID: c8a3e6f10b57
Revises: b3f7c1d9a482
Create Date: 2026-08-28 00:00:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c8a3e6f10b57"
down_revision = "b3f7c1d9a482"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Plain rename — no new default/backfill needed, every existing tenant row keeps
    # its current value under the new name. The toggle now governs whether a waiter is
    # required before billing on *either* POS layout (previously Guided-POS-only);
    # Default layout's own always-mandatory hardcoding is removed at the application
    # layer in the same change, so this rename is the only DB-level piece.
    op.alter_column(
        "tenants", "guided_pos_waiter_mandatory_enabled", new_column_name="waiter_mandatory_enabled"
    )


def downgrade() -> None:
    op.alter_column(
        "tenants", "waiter_mandatory_enabled", new_column_name="guided_pos_waiter_mandatory_enabled"
    )
