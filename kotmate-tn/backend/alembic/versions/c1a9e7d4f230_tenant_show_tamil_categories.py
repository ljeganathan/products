"""tenant show_tamil_categories toggle

Revision ID: c1a9e7d4f230
Revises: b8f4d2a91c67
Create Date: 2026-08-14 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1a9e7d4f230'
down_revision: Union[str, None] = 'b8f4d2a91c67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'tenants',
        sa.Column('show_tamil_categories', sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.alter_column('tenants', 'show_tamil_categories', server_default=None)


def downgrade() -> None:
    op.drop_column('tenants', 'show_tamil_categories')
