"""order party label

Revision ID: 5a1c3e8f2d67
Revises: 2f7b9c4d8a1e
Create Date: 2026-08-08 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5a1c3e8f2d67'
down_revision: Union[str, None] = '2f7b9c4d8a1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('party_label', sa.String(length=30), nullable=True))
    op.create_index(
        'uq_orders_open_table_party',
        'orders',
        ['tenant_id', 'table_id', 'party_label'],
        unique=True,
        postgresql_where=sa.text("status = 'open' AND table_id IS NOT NULL AND party_label IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index('uq_orders_open_table_party', table_name='orders')
    op.drop_column('orders', 'party_label')
