"""add tamil item name support

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'company_settings',
        sa.Column(
            'show_tamil_item_names',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column('bill_items', sa.Column('item_name_ta_snapshot', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('bill_items', 'item_name_ta_snapshot')
    op.drop_column('company_settings', 'show_tamil_item_names')
