"""qr self-order: table_qr_codes, guest_sessions, orders.source, users.is_system_account

Revision ID: a7c3f91b2d04
Revises: d4b8f2a91c6e
Create Date: 2026-09-06 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "a7c3f91b2d04"
down_revision = "d4b8f2a91c6e"
branch_labels = None
depends_on = None

_POLICY_EXPR = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid "
    "OR current_setting('app.is_platform_admin', true) = 'true'"
)


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""
        CREATE POLICY tenant_isolation ON {table_name}
        USING ({_POLICY_EXPR})
        WITH CHECK ({_POLICY_EXPR});
        """
    )


def _disable_rls(table_name: str) -> None:
    op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table_name};")
    op.execute(f"ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;")


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("qr_self_order_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("tenants", "qr_self_order_enabled", server_default=None)

    # Additive, defaults every existing order to 'staff' — zero behavior change.
    op.add_column("orders", sa.Column("source", sa.String(10), nullable=False, server_default="staff"))
    op.alter_column("orders", "source", server_default=None)
    op.create_check_constraint("ck_orders_source_valid", "orders", "source IN ('staff', 'guest')")

    op.add_column(
        "users",
        sa.Column("is_system_account", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("users", "is_system_account", server_default=None)

    # One row per TABLE (production feedback: a separate physical QR per seat is not
    # operationally maintainable for a restaurant to print/laminate/replace) — a single
    # printed code per table. Whoever scans it shares the table's one active guest
    # order; there's no customer-number concept to resolve or assign.
    op.create_table(
        "table_qr_codes",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("table_id", sa.UUID(), nullable=False),
        sa.Column("qr_token", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["tenant_locations.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("table_id", name="uq_table_qr_codes_table"),
        sa.UniqueConstraint("qr_token", name="uq_table_qr_codes_qr_token"),
    )
    op.create_index("ix_table_qr_codes_tenant_id_id", "table_qr_codes", ["tenant_id", "id"])
    _enable_rls("table_qr_codes")

    # One row = the table's single shared ordering session — no party_label/seat
    # concept at all (that's a separate, staff-side-only feature, CLAUDE.md §11's
    # CustomerSelectorBar; a QR self-order table always orders as one party/one bill).
    op.create_table(
        "guest_sessions",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("table_id", sa.UUID(), nullable=False),
        sa.Column("customer_name", sa.String(100), nullable=True),
        sa.Column("customer_phone", sa.String(20), nullable=True),
        sa.Column("order_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'payment_claimed', 'closed')", name="ck_guest_sessions_status_valid"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["tenant_locations.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["tables.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_guest_sessions_tenant_id_id", "guest_sessions", ["tenant_id", "id"])
    # At most one *active* session per table — any scan of that table's one QR either
    # joins this row or (once it's closed by a staff bill finalize) starts the next one.
    op.execute(
        "CREATE UNIQUE INDEX uq_guest_sessions_active_table "
        "ON guest_sessions (tenant_id, table_id) WHERE status = 'active'"
    )
    _enable_rls("guest_sessions")

    # Pro Max only (CLAUDE.md §6), same data-only JSONB-merge shape as phase-22's
    # ffa2fb832bd7 for stock_management.
    op.execute(
        sa.text(
            "UPDATE plans SET features = features || '{\"qr_self_order\": true}'::jsonb "
            "WHERE code = 'pro_max'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE plans SET features = features || '{\"qr_self_order\": false}'::jsonb "
            "WHERE code = 'pro_max'"
        )
    )
    _disable_rls("guest_sessions")
    op.execute("DROP INDEX IF EXISTS uq_guest_sessions_active_table")
    op.drop_index("ix_guest_sessions_tenant_id_id", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    _disable_rls("table_qr_codes")
    op.drop_index("ix_table_qr_codes_tenant_id_id", table_name="table_qr_codes")
    op.drop_table("table_qr_codes")
    op.drop_column("users", "is_system_account")
    op.drop_constraint("ck_orders_source_valid", "orders", type_="check")
    op.drop_column("orders", "source")
    op.drop_column("tenants", "qr_self_order_enabled")
