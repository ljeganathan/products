"""online payments: per-tenant gateway settings, payment attempts, payments.reference

Revision ID: e5b2c7d91a34
Revises: d3f6a1c8b942
Create Date: 2026-09-26 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = "e5b2c7d91a34"
down_revision = "d3f6a1c8b942"
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


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    # Additive only: two new tables and one nullable column. No existing row is read,
    # changed or backfilled, so tenants that never enable online payments are unaffected.
    op.create_table(
        "tenant_payment_gateways",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False, server_default="razorpay"),
        # 'api_keys' = the hotel's own Razorpay key id/secret (Model A). 'partner_oauth'
        # is reserved for Razorpay's Partner program (Model B), where `secret_encrypted`
        # would hold the sub-merchant's OAuth access token instead — see
        # services/payment_gateway.py, the single place that reads it.
        sa.Column("auth_mode", sa.String(20), nullable=False, server_default="api_keys"),
        sa.Column("key_id", sa.String(100), nullable=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=True),
        sa.Column("webhook_secret_encrypted", sa.Text(), nullable=True),
        # Provider-side account reference (e.g. a Partner sub-merchant's account id).
        sa.Column("account_ref", sa.String(100), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.UUID(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", name="uq_tenant_payment_gateways_tenant"),
    )
    op.create_index("ix_tenant_payment_gateways_tenant_id_id", "tenant_payment_gateways", ["tenant_id", "id"])
    _enable_rls("tenant_payment_gateways")

    op.create_table(
        "payment_attempts",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("guest_session_id", sa.UUID(), nullable=True),
        sa.Column("bill_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_order_id", sa.String(64), nullable=False),
        sa.Column("provider_payment_id", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(12), nullable=False, server_default="created"),
        sa.Column("method", sa.String(20), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["guest_session_id"], ["guest_sessions.id"]),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('created', 'paid', 'failed')", name="ck_payment_attempts_status_valid"),
        sa.UniqueConstraint("provider", "provider_order_id", name="uq_payment_attempts_provider_order"),
    )
    op.create_index("ix_payment_attempts_tenant_id_id", "payment_attempts", ["tenant_id", "id"])
    op.create_index("ix_payment_attempts_tenant_order", "payment_attempts", ["tenant_id", "order_id"])
    _enable_rls("payment_attempts")

    # Gateway payment reference on the bill's payment line (reconciliation). Nullable:
    # cash/card/manual UPI lines simply have none.
    op.add_column("payments", sa.Column("reference", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("payments", "reference")
    _disable_rls("payment_attempts")
    op.drop_index("ix_payment_attempts_tenant_order", table_name="payment_attempts")
    op.drop_index("ix_payment_attempts_tenant_id_id", table_name="payment_attempts")
    op.drop_table("payment_attempts")
    _disable_rls("tenant_payment_gateways")
    op.drop_index("ix_tenant_payment_gateways_tenant_id_id", table_name="tenant_payment_gateways")
    op.drop_table("tenant_payment_gateways")
