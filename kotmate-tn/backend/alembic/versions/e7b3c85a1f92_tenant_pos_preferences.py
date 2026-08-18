"""tenant pos preferences

Revision ID: e7b3c85a1f92
Revises: d2f6a91c4e58
Create Date: 2026-08-18 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7b3c85a1f92'
down_revision: Union[str, None] = 'd2f6a91c4e58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('default_payment_method', sa.String(10), nullable=False, server_default='cash'),
    )
    op.alter_column('tenants', 'default_payment_method', server_default=None)
    op.create_check_constraint(
        'ck_tenants_default_payment_method_valid',
        'tenants',
        "default_payment_method IN ('upi', 'cash', 'card')",
    )

    op.add_column(
        'tenants',
        sa.Column('report_printing_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('tenants', 'report_printing_enabled', server_default=None)


def downgrade() -> None:
    op.drop_constraint('ck_tenants_default_payment_method_valid', 'tenants', type_='check')
    op.drop_column('tenants', 'default_payment_method')
    op.drop_column('tenants', 'report_printing_enabled')
