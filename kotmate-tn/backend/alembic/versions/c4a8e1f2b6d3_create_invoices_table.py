"""create invoices table

Revision ID: c4a8e1f2b6d3
Revises: 7b3f0c2a1e9d
Create Date: 2026-08-08 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4a8e1f2b6d3'
down_revision: Union[str, None] = '7b3f0c2a1e9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_POLICY_EXPR = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid "
    "OR current_setting('app.is_platform_admin', true) = 'true'"
)


def upgrade() -> None:
    op.create_table(
        'invoices',
        sa.Column('tenant_id', sa.UUID(), nullable=False),
        sa.Column('subscription_id', sa.UUID(), nullable=True),
        sa.Column('invoice_number', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('issued_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('paid_date', sa.Date(), nullable=True),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('draft', 'sent', 'paid', 'overdue')",
            name=op.f('ck_invoices_ck_invoices_status_valid'),
        ),
        sa.ForeignKeyConstraint(
            ['subscription_id'], ['subscriptions.id'], name=op.f('fk_invoices_subscription_id_subscriptions')
        ),
        sa.ForeignKeyConstraint(
            ['tenant_id'], ['tenants.id'], name=op.f('fk_invoices_tenant_id_tenants'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
        sa.UniqueConstraint('invoice_number', name=op.f('uq_invoices_invoice_number')),
    )
    op.create_index('ix_invoices_tenant_id_id', 'invoices', ['tenant_id', 'id'], unique=False)
    op.create_index('ix_invoices_due_date_status', 'invoices', ['due_date', 'status'], unique=False)

    # Row-level security, same pattern as dd586dfba4be for every other tenant-scoped
    # table (CLAUDE.md §4) — invoices didn't exist yet when that migration ran.
    op.execute("ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE invoices FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON invoices
        USING ({_POLICY_EXPR})
        WITH CHECK ({_POLICY_EXPR});
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invoices;")
    op.execute("ALTER TABLE invoices NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE invoices DISABLE ROW LEVEL SECURITY;")
    op.drop_index('ix_invoices_due_date_status', table_name='invoices')
    op.drop_index('ix_invoices_tenant_id_id', table_name='invoices')
    op.drop_table('invoices')
