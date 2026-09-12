"""items: remember the Stock Management calculator's per-item conversion (qty + unit)

Revision ID: b8e21f6a9c34
Revises: a7c3f91b2d04
Create Date: 2026-09-12 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b8e21f6a9c34"
down_revision = "a7c3f91b2d04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Both nullable, no server_default needed — every existing item simply has neither
    # set (exactly today's behavior: the calculator opens blank) until a cashier/admin
    # runs the "Calculate for Me" flow for it once. Zero impact on any existing item,
    # tenant, or production data.
    op.add_column("items", sa.Column("stock_calc_qty", sa.Numeric(10, 3), nullable=True))
    op.add_column("items", sa.Column("stock_calc_unit", sa.String(10), nullable=True))
    op.create_check_constraint(
        "ck_items_stock_calc_unit",
        "items",
        "stock_calc_unit IS NULL OR stock_calc_unit IN ('g', 'kg', 'ml', 'l', 'pcs')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_items_stock_calc_unit", "items", type_="check")
    op.drop_column("items", "stock_calc_unit")
    op.drop_column("items", "stock_calc_qty")
