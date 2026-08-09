"""stock ledger and tenant toggle

Revision ID: 5d52cf46dd81
Revises: 12432d67bb20
Create Date: 2026-08-09 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d52cf46dd81'
down_revision: Union[str, None] = '12432d67bb20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_EXPR = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid "
    "OR current_setting('app.is_platform_admin', true) = 'true'"
)


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('stock_management_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('tenants', 'stock_management_enabled', server_default=None)

    op.create_table(
        'stock_ledger',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('item_id', sa.UUID(), nullable=False),
        sa.Column('location_id', sa.UUID(), nullable=True),
        sa.Column('change_qty', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=20), nullable=False),
        sa.Column('reference_order_id', sa.UUID(), nullable=True),
        sa.Column('reference_bill_id', sa.UUID(), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "reason IN ('manual_set', 'kot_deduction', 'restock')",
            name=op.f('ck_stock_ledger_ck_stock_ledger_reason_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name=op.f('fk_stock_ledger_tenant_id_tenants'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['item_id'], ['items.id'], name=op.f('fk_stock_ledger_item_id_items')),
        sa.ForeignKeyConstraint(
            ['location_id'], ['tenant_locations.id'], name=op.f('fk_stock_ledger_location_id_tenant_locations')
        ),
        sa.ForeignKeyConstraint(
            ['reference_order_id'], ['orders.id'], name=op.f('fk_stock_ledger_reference_order_id_orders')
        ),
        sa.ForeignKeyConstraint(
            ['reference_bill_id'], ['bills.id'], name=op.f('fk_stock_ledger_reference_bill_id_bills')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_stock_ledger')),
    )
    op.create_index('ix_stock_ledger_tenant_id_id', 'stock_ledger', ['tenant_id', 'id'], unique=False)

    # Row-level security, same pattern as dd586dfba4be for every other tenant-scoped
    # table (CLAUDE.md §4) — stock_ledger didn't exist yet when that migration ran.
    op.execute("ALTER TABLE stock_ledger ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE stock_ledger FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON stock_ledger
        USING ({_POLICY_EXPR})
        WITH CHECK ({_POLICY_EXPR});
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON stock_ledger;")
    op.execute("ALTER TABLE stock_ledger NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE stock_ledger DISABLE ROW LEVEL SECURITY;")
    op.drop_index('ix_stock_ledger_tenant_id_id', table_name='stock_ledger')
    op.drop_table('stock_ledger')
    op.drop_column('tenants', 'stock_management_enabled')
