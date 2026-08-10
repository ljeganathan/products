"""hotel_master receipt footer message

Revision ID: f1a2b3c4d5e6
Revises: 83c69be1edbf
Create Date: 2026-08-10 09:00:00.000000

Printer fixes batch: a tenant-editable closing message (e.g. "Thank You & Visit
Again..!!!") printed centered near the end of the bill, alongside the existing
logo/GSTIN/UPI/Tamil-toggle fields on hotel_master.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "83c69be1edbf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotel_master", sa.Column("receipt_footer_message", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("hotel_master", "receipt_footer_message")
