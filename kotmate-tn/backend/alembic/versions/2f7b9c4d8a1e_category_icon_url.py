"""category icon url

Revision ID: 2f7b9c4d8a1e
Revises: 9e2d5a7c0f14
Create Date: 2026-08-08 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f7b9c4d8a1e'
down_revision: Union[str, None] = '9e2d5a7c0f14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('icon_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('categories', 'icon_url')
