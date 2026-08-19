"""tenant report tamil names toggle

Revision ID: db07d0c0058e
Revises: b7e2a6f905dc
Create Date: 2026-08-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "db07d0c0058e"
down_revision = "b7e2a6f905dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default backfills every existing tenant row to False in the same statement;
    # dropping the default afterward means future inserts must supply it explicitly via
    # the ORM (Tenant.report_tamil_names_enabled's own `default=False`) — same two-step
    # shape already used for report_printing_enabled/stock_management_enabled.
    op.add_column(
        "tenants",
        sa.Column("report_tamil_names_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("tenants", "report_tamil_names_enabled", server_default=None)


def downgrade() -> None:
    op.drop_column("tenants", "report_tamil_names_enabled")
