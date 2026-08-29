"""guided pos layout, waiter-mandatory toggle, and kot ticket billed-via-kot flag

Revision ID: b3f7c1d9a482
Revises: a1c9e4d7b3f2
Create Date: 2026-08-27 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b3f7c1d9a482"
down_revision = "a1c9e4d7b3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills every existing tenant row to 'default' in the same
    # statement (today's layout, unchanged), then the default is dropped so every
    # future insert must supply it explicitly via the ORM — same two-step shape already
    # used for every additive column in this codebase (e.g. report_tamil_names_enabled).
    op.add_column(
        "tenants",
        sa.Column("pos_layout", sa.String(20), nullable=False, server_default="default"),
    )
    op.alter_column("tenants", "pos_layout", server_default=None)
    op.create_check_constraint(
        "ck_tenants_pos_layout_valid", "tenants", "pos_layout IN ('default', 'guided')"
    )

    # Defaults true to match Default layout's existing always-mandatory waiter
    # requirement — switching a tenant to Guided POS changes nothing about this by
    # itself until the tenant_admin explicitly turns it off in Settings.
    op.add_column(
        "tenants",
        sa.Column(
            "guided_pos_waiter_mandatory_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("tenants", "guided_pos_waiter_mandatory_enabled", server_default=None)

    op.add_column(
        "kot_tickets",
        sa.Column("order_billed_via_kot", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("kot_tickets", "order_billed_via_kot", server_default=None)


def downgrade() -> None:
    op.drop_column("kot_tickets", "order_billed_via_kot")
    op.drop_constraint("ck_tenants_pos_layout_valid", "tenants", type_="check")
    op.drop_column("tenants", "guided_pos_waiter_mandatory_enabled")
    op.drop_column("tenants", "pos_layout")
