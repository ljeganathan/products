"""add pincode to company_settings

Revision ID: a1b2c3d4e5f6
Revises: f45fbdc3e7ec
Create Date: 2026-07-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f45fbdc3e7ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('company_settings', sa.Column('pincode', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('company_settings', 'pincode')
