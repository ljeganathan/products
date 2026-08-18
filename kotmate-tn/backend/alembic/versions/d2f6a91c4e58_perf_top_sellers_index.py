"""perf top sellers index

Revision ID: d2f6a91c4e58
Revises: c1a9e7d4f230
Create Date: 2026-08-18 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd2f6a91c4e58'
down_revision: Union[str, None] = 'c1a9e7d4f230'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Powers the POS "Top Selling" tab's switch from a 7-day to a 1-hour rolling
    # window (item_service.list_top_sellers) — without this, that query's
    # `Bill.created_at >= cutoff` filter has no index to seek into and falls back to
    # scanning every tenant-scoped bill row.
    op.create_index(
        'ix_bills_tenant_id_created_at', 'bills', ['tenant_id', 'created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_bills_tenant_id_created_at', table_name='bills')
