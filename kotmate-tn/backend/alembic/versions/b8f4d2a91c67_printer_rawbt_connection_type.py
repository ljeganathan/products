"""printer rawbt connection type

Revision ID: b8f4d2a91c67
Revises: a7c3e9f01b45
Create Date: 2026-08-13 06:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f4d2a91c67"
down_revision: Union[str, None] = "a7c3e9f01b45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_printers_ck_printers_connection_type_valid"), "printers", type_="check")
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_connection_type_valid "
        "CHECK (connection_type IN ('network', 'usb', 'local_agent', 'wifi', 'bluetooth', 'rawbt'))"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_printers_ck_printers_connection_type_valid"), "printers", type_="check")
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_connection_type_valid "
        "CHECK (connection_type IN ('network', 'usb', 'local_agent', 'wifi', 'bluetooth'))"
    )
