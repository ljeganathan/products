"""plan pricing update

Revision ID: a7c3e9f01b45
Revises: f1a2b3c4d5e6
Create Date: 2026-08-12 09:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f01b45"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (code, old_monthly, old_yearly, new_monthly, new_yearly)
PRICING = [
    ("lite", 999, 9990, 499, 4999),
    ("pro", 2499, 24990, 799, 7999),
    ("pro_max", 4999, 49990, 1499, 14999),
]


def upgrade() -> None:
    # Data-only: revised go-to-market pricing (product decision, replacing the original
    # a20112fa8ba8 seed anchor prices) — max_users/max_locations/features are unchanged
    # by this migration, only price_monthly/price_yearly move.
    for code, _, _, new_monthly, new_yearly in PRICING:
        op.execute(
            sa.text(
                "UPDATE plans SET price_monthly = :monthly, price_yearly = :yearly WHERE code = :code"
            ).bindparams(monthly=new_monthly, yearly=new_yearly, code=code)
        )


def downgrade() -> None:
    for code, old_monthly, old_yearly, _, _ in PRICING:
        op.execute(
            sa.text(
                "UPDATE plans SET price_monthly = :monthly, price_yearly = :yearly WHERE code = :code"
            ).bindparams(monthly=old_monthly, yearly=old_yearly, code=code)
        )
