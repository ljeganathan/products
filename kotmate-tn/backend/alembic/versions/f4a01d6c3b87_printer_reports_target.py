"""printer reports target

Revision ID: f4a01d6c3b87
Revises: e7b3c85a1f92
Create Date: 2026-08-18 09:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f4a01d6c3b87'
down_revision: Union[str, None] = 'e7b3c85a1f92'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Widen only — every existing 'kot'/'bill' row stays valid under the new
    # constraint, nothing to backfill. Uses op.f() since the constraint was
    # originally created with a doubled ck_printers_ck_printers_* prefix from
    # Alembic's naming convention (see 5cadf97c7c21_initial_schema.py) — the same
    # gotcha b8f4d2a91c67_printer_rawbt_connection_type.py already worked around.
    op.drop_constraint(op.f('ck_printers_ck_printers_target_valid'), 'printers', type_='check')
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_target_valid "
        "CHECK (target IN ('kot', 'bill', 'reports'))"
    )
    # Additive JSONB merge, pro_max only — doesn't touch lite/pro or any other
    # existing key already on pro_max's features.
    op.execute(
        "UPDATE plans SET features = features || '{\"report_printing\": true}'::jsonb "
        "WHERE code = 'pro_max'"
    )


def downgrade() -> None:
    op.execute("UPDATE plans SET features = features - 'report_printing' WHERE code = 'pro_max'")
    op.drop_constraint(op.f('ck_printers_ck_printers_target_valid'), 'printers', type_='check')
    op.execute(
        "ALTER TABLE printers ADD CONSTRAINT ck_printers_ck_printers_target_valid "
        "CHECK (target IN ('kot', 'bill'))"
    )
