"""stock ledger bill_deduction reason

Revision ID: 83c69be1edbf
Revises: 2e705ea88865
Create Date: 2026-08-09 16:00:00.000000

Direct POS billing (no prior KOT send) was a gap in stock deduction — only KOT-send
decremented stock, so an item billed straight from the cart never decremented. Bill
finalize now also deducts stock for any order_item that was never KOT-sent, logged with
a new `bill_deduction` reason (distinct from `kot_deduction`) so the ledger accurately
shows what triggered each change.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83c69be1edbf"
down_revision: Union[str, None] = "2e705ea88865"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_stock_ledger_ck_stock_ledger_reason_valid"), "stock_ledger", type_="check")
    op.create_check_constraint(
        op.f("ck_stock_ledger_ck_stock_ledger_reason_valid"),
        "stock_ledger",
        "reason IN ('manual_set', 'kot_deduction', 'restock', 'bill_deduction')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_stock_ledger_ck_stock_ledger_reason_valid"), "stock_ledger", type_="check")
    op.create_check_constraint(
        op.f("ck_stock_ledger_ck_stock_ledger_reason_valid"),
        "stock_ledger",
        "reason IN ('manual_set', 'kot_deduction', 'restock')",
    )
