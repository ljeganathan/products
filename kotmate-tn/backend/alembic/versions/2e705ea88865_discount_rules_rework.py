"""discount rules rework

Revision ID: 2e705ea88865
Revises: ffa2fb832bd7
Create Date: 2026-08-09 15:00:00.000000

Adds discount_mode/item_id/expires_at to discount_rules (Phase 23: rule-driven
auto-applying discounts, replacing the old fully-manual-at-bill-time flow) and
discount_note to bills (persisted breakdown of which rule(s) applied, for reprint
fidelity). Existing discount_rules rows default discount_mode='percent', preserving
today's percent-only behavior.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2e705ea88865"
down_revision: Union[str, None] = "ffa2fb832bd7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "discount_rules",
        sa.Column("discount_mode", sa.String(length=10), nullable=False, server_default="percent"),
    )
    op.add_column("discount_rules", sa.Column("item_id", sa.UUID(), nullable=True))
    op.add_column("discount_rules", sa.Column("expires_at", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_discount_rules_mode_valid", "discount_rules", "discount_mode IN ('percent', 'rupee')"
    )
    op.create_foreign_key(
        op.f("fk_discount_rules_item_id_items"), "discount_rules", "items", ["item_id"], ["id"]
    )

    op.add_column("bills", sa.Column("discount_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bills", "discount_note")

    op.drop_constraint(op.f("fk_discount_rules_item_id_items"), "discount_rules", type_="foreignkey")
    op.drop_constraint("ck_discount_rules_mode_valid", "discount_rules", type_="check")
    op.drop_column("discount_rules", "expires_at")
    op.drop_column("discount_rules", "item_id")
    op.drop_column("discount_rules", "discount_mode")
