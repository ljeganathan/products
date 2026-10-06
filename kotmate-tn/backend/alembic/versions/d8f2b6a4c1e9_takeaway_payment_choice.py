"""Takeaway guest orders record how the guest chose to pay (online first, or cash at the counter).

Revision ID: d8f2b6a4c1e9
Revises: c4e8a2d6b1f7
Create Date: 2026-10-06 12:00:00.000000

Production-safe: adds one nullable column and one check. Existing rows stay NULL, which the
POS list treats exactly as before (a takeaway order with items shows up for the counter).
"""

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision = "d8f2b6a4c1e9"
down_revision = "c4e8a2d6b1f7"
branch_labels = None
depends_on = None

# The exact database name (the model's naming convention doubles the table prefix).
_TAKEAWAY_PAYMENT_CK = conv("ck_guest_sessions_ck_guest_sessions_takeaway_payment_valid")


def upgrade() -> None:
    op.add_column("guest_sessions", sa.Column("takeaway_payment", sa.String(10), nullable=True))
    op.create_check_constraint(
        _TAKEAWAY_PAYMENT_CK,
        "guest_sessions",
        "takeaway_payment IS NULL OR takeaway_payment IN ('online', 'cash')",
    )


def downgrade() -> None:
    op.drop_constraint(_TAKEAWAY_PAYMENT_CK, "guest_sessions", type_="check")
    op.drop_column("guest_sessions", "takeaway_payment")
