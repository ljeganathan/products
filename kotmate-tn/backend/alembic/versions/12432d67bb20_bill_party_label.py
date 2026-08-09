"""bill party label

Revision ID: 12432d67bb20
Revises: 9c46b3480166
Create Date: 2026-08-09 08:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "12432d67bb20"
down_revision: Union[str, None] = "9c46b3480166"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("bills", sa.Column("party_label", sa.String(length=30), nullable=True))


def downgrade() -> None:
    op.drop_column("bills", "party_label")
