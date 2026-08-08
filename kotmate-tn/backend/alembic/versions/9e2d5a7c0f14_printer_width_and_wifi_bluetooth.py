"""printer width and wifi/bluetooth connection types

Revision ID: 9e2d5a7c0f14
Revises: c4a8e1f2b6d3
Create Date: 2026-08-08 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e2d5a7c0f14'
down_revision: Union[str, None] = 'c4a8e1f2b6d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('printers', sa.Column('paper_width_mm', sa.Integer(), nullable=True))
    op.drop_constraint(op.f('ck_printers_ck_printers_connection_type_valid'), 'printers', type_='check')
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_connection_type_valid "
        "CHECK (connection_type IN ('network', 'usb', 'local_agent', 'wifi', 'bluetooth'))"
    )


def downgrade() -> None:
    op.drop_constraint(op.f('ck_printers_ck_printers_connection_type_valid'), 'printers', type_='check')
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_connection_type_valid "
        "CHECK (connection_type IN ('network', 'usb', 'local_agent'))"
    )
    op.drop_column('printers', 'paper_width_mm')
