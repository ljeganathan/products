"""plan features: pos_operator_role (pro_max only) + tighten kds to pro_max only

Revision ID: b7e2a6f905dc
Revises: a5c8f1d4e93b
Create Date: 2026-08-20 09:05:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b7e2a6f905dc'
down_revision: Union[str, None] = 'a5c8f1d4e93b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Additive JSONB merge, pro_max only.
    op.execute(
        "UPDATE plans SET features = features || '{\"pos_operator_role\": true}'::jsonb "
        "WHERE code = 'pro_max'"
    )
    # Pro was seeded with kds=true (a20112fa8ba8) — tightening the KOT screen/KDS to
    # Pro Max only per production feedback round 2. Lite is already kds=false, untouched.
    op.execute("UPDATE plans SET features = jsonb_set(features, '{kds}', 'false'::jsonb) WHERE code = 'pro'")


def downgrade() -> None:
    op.execute("UPDATE plans SET features = jsonb_set(features, '{kds}', 'true'::jsonb) WHERE code = 'pro'")
    op.execute("UPDATE plans SET features = features - 'pos_operator_role' WHERE code = 'pro_max'")
