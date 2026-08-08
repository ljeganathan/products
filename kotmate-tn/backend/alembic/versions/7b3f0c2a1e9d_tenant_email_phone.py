"""tenant email phone

Revision ID: 7b3f0c2a1e9d
Revises: c2cd2c36eb0d
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b3f0c2a1e9d'
down_revision: Union[str, None] = 'c2cd2c36eb0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('email', sa.String(length=200), nullable=True))
    op.add_column('tenants', sa.Column('phone', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'phone')
    op.drop_column('tenants', 'email')
