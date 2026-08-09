"""stock management plan feature

Revision ID: ffa2fb832bd7
Revises: 5d52cf46dd81
Create Date: 2026-08-09 09:05:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ffa2fb832bd7"
down_revision: Union[str, None] = "5d52cf46dd81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only: stock-quantity management (CLAUDE.md §11 extension) is Pro/Pro Max
    # only — Lite never sees the Settings toggle, the KOT screen's Stock Management
    # tab, or any stock badges, matching the item_import precedent (9c46b3480166).
    op.execute(
        sa.text(
            "UPDATE plans SET features = features || '{\"stock_management\": true}'::jsonb "
            "WHERE code IN ('pro', 'pro_max')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE plans SET features = features || '{\"stock_management\": false}'::jsonb "
            "WHERE code IN ('pro', 'pro_max')"
        )
    )
