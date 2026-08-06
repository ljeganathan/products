"""trigram search index on items

Revision ID: 95a490b62fde
Revises: 1d9a272d7771
Create Date: 2026-08-05 15:58:08.965435

Powers `GET /api/v1/items/search` (Phase 07, CLAUDE.md §9 item-code/search quick entry)
— trigram similarity keeps a 500-item catalog search under the <300ms perceived-latency
budget even for typo-tolerant partial matches, which a plain B-tree/ILIKE can't do.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '95a490b62fde'
down_revision: Union[str, None] = '1d9a272d7771'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX ix_items_name_en_trgm ON items USING gin (name_en gin_trgm_ops)"
    )
    op.execute(
        "CREATE INDEX ix_items_name_ta_trgm ON items USING gin (name_ta gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_items_name_ta_trgm")
    op.execute("DROP INDEX IF EXISTS ix_items_name_en_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
