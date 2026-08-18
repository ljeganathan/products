"""seed pos_operator role

Revision ID: a5c8f1d4e93b
Revises: f4a01d6c3b87
Create Date: 2026-08-20 09:00:00.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a5c8f1d4e93b'
down_revision: Union[str, None] = 'f4a01d6c3b87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same ad-hoc table shape as a20112fa8ba8_seed_plans_and_roles.py — frozen in time,
# independent of app.models.user.Role.
roles_table = sa.table(
    "roles",
    sa.column("id", PgUUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
)


def upgrade() -> None:
    # New POS-screen-only role (production feedback round 2) — Pro Max only, gated via
    # the pro_max-only "pos_operator_role" plan feature added in the next migration.
    # roles.code has no CHECK constraint (only UNIQUE), so this is a plain data insert.
    op.bulk_insert(roles_table, [{"id": uuid.uuid4(), "code": "pos_operator", "name": "POS Operator"}])


def downgrade() -> None:
    # Safe only if no user currently has this role — the FK (users.role_id -> roles.id)
    # would already block this delete otherwise.
    op.execute(sa.text("DELETE FROM roles WHERE code = 'pos_operator'"))
