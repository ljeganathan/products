"""Kiosk role + kiosk-sourced self-order sessions.

Revision ID: d2f6b8a1c4e9
Revises: e1a5c9d3b7f2
Create Date: 2026-10-14 00:00:00.000000

Production-safe by construction: a new role row, a new column with a default (every
existing guest_sessions row becomes is_kiosk=false), and a widened allowed-value list
on orders.source. No existing row is updated or deleted.
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.sql.elements import conv

from alembic import op

revision: str = "d2f6b8a1c4e9"
down_revision: Union[str, None] = "e1a5c9d3b7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Same ad-hoc table shape as a5c8f1d4e93b_seed_pos_operator_role.py — frozen in time,
# independent of app.models.user.Role.
roles_table = sa.table(
    "roles",
    sa.column("id", PgUUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
)

# Exact name already in the database (the model's naming convention doubles the table
# prefix), so op.f()/conv() keeps it literal rather than re-deriving/truncating it.
_ORDERS_SOURCE_CK = conv("ck_orders_ck_orders_source_valid")
_OLD_SOURCES = "('staff', 'guest')"
_NEW_SOURCES = "('staff', 'guest', 'kiosk')"


def upgrade() -> None:
    op.bulk_insert(roles_table, [{"id": uuid.uuid4(), "code": "kiosk", "name": "Kiosk"}])

    op.add_column(
        "guest_sessions", sa.Column("is_kiosk", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.alter_column("guest_sessions", "is_kiosk", server_default=None)

    op.drop_constraint(_ORDERS_SOURCE_CK, "orders", type_="check")
    op.create_check_constraint(_ORDERS_SOURCE_CK, "orders", f"source IN {_NEW_SOURCES}")


def downgrade() -> None:
    # Fails loudly if any row already uses 'kiosk' (an order or a guest session) —
    # nothing is deleted to make it pass.
    op.drop_constraint(_ORDERS_SOURCE_CK, "orders", type_="check")
    op.create_check_constraint(_ORDERS_SOURCE_CK, "orders", f"source IN {_OLD_SOURCES}")

    op.drop_column("guest_sessions", "is_kiosk")

    op.execute(sa.text("DELETE FROM roles WHERE code = 'kiosk'"))
