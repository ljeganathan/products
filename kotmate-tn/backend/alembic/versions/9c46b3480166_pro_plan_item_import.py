"""pro plan item import

Revision ID: 9c46b3480166
Revises: 5a1c3e8f2d67
Create Date: 2026-08-09 08:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c46b3480166"
down_revision: Union[str, None] = "5a1c3e8f2d67"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Data-only change (Phase 21, product decision): Pro tenants now get Item Master
    # CSV import too, not just export — only Lite remains without it. Uses a JSONB
    # merge rather than reconstructing the whole `features` dict, so it only flips this
    # one key regardless of what else has changed in `features` since the original seed
    # (a20112fa8ba8) or via later Product Owner console edits.
    op.execute(
        sa.text("UPDATE plans SET features = features || '{\"item_import\": true}'::jsonb WHERE code = 'pro'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE plans SET features = features || '{\"item_import\": false}'::jsonb WHERE code = 'pro'")
    )
