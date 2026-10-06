"""Cashfree as a second online payment provider, and 'online' as a bill payment method.

Revision ID: c4e8a2d6b1f7
Revises: f1a3c8e2b567
Create Date: 2026-10-06 00:00:00.000000

Production-safe by construction: every change only adds a column, widens an allowed-value
list, or swaps one uniqueness rule for a looser one. No existing row is updated or deleted.
Existing tenants keep their one Razorpay row (still enabled if it was), and their existing
'upi' / 'cash' / 'card' bill lines are untouched.

Check-constraint names are the exact names already in the database (the model's naming
convention doubles the table prefix), so op.f() keeps them literal.
"""

import sqlalchemy as sa
from sqlalchemy.sql.elements import conv

from alembic import op

revision = "c4e8a2d6b1f7"
down_revision = "f1a3c8e2b567"
branch_labels = None
depends_on = None

_OLD_METHODS = "('upi', 'cash', 'card')"
_NEW_METHODS = "('upi', 'cash', 'card', 'online')"

_PAYMENTS_METHOD_CK = conv("ck_payments_ck_payments_method_valid")
_TENANTS_DEFAULT_METHOD_CK = conv("ck_tenants_ck_tenants_default_payment_method_valid")
_GATEWAY_PROVIDER_CK = conv("ck_tenant_payment_gateways_ck_tenant_pg_provider_valid")


def upgrade() -> None:
    # Cashfree's explicit sandbox/production switch. NULL for every existing (Razorpay) row.
    op.add_column("tenant_payment_gateways", sa.Column("environment", sa.String(10), nullable=True))

    # One row per (tenant, provider) instead of one row per tenant. Existing rows all have
    # provider='razorpay' and at most one per tenant, so the new uniqueness already holds.
    op.drop_constraint("uq_tenant_payment_gateways_tenant", "tenant_payment_gateways", type_="unique")
    op.create_unique_constraint(
        "uq_tenant_payment_gateways_tenant_provider", "tenant_payment_gateways", ["tenant_id", "provider"]
    )
    # At most one enabled provider per tenant. Existing enabled Razorpay rows are unaffected.
    op.create_index(
        "uq_tenant_payment_gateways_one_enabled",
        "tenant_payment_gateways",
        ["tenant_id"],
        unique=True,
        postgresql_where=sa.text("is_enabled"),
    )
    op.create_check_constraint(_GATEWAY_PROVIDER_CK, "tenant_payment_gateways", "provider IN ('razorpay', 'cashfree')")

    # 'online' as a bill payment method. Every existing value still passes the wider list.
    op.drop_constraint(_PAYMENTS_METHOD_CK, "payments", type_="check")
    op.create_check_constraint(_PAYMENTS_METHOD_CK, "payments", f"method IN {_NEW_METHODS}")

    op.drop_constraint(_TENANTS_DEFAULT_METHOD_CK, "tenants", type_="check")
    op.create_check_constraint(_TENANTS_DEFAULT_METHOD_CK, "tenants", f"default_payment_method IN {_NEW_METHODS}")


def downgrade() -> None:
    # Fails loudly if any row already uses the new values (e.g. an 'online' bill line or a
    # Cashfree row). Nothing is deleted to make it pass.
    op.drop_constraint(_TENANTS_DEFAULT_METHOD_CK, "tenants", type_="check")
    op.create_check_constraint(_TENANTS_DEFAULT_METHOD_CK, "tenants", f"default_payment_method IN {_OLD_METHODS}")

    op.drop_constraint(_PAYMENTS_METHOD_CK, "payments", type_="check")
    op.create_check_constraint(_PAYMENTS_METHOD_CK, "payments", f"method IN {_OLD_METHODS}")

    op.drop_constraint(_GATEWAY_PROVIDER_CK, "tenant_payment_gateways", type_="check")
    op.drop_index("uq_tenant_payment_gateways_one_enabled", table_name="tenant_payment_gateways")
    op.drop_constraint("uq_tenant_payment_gateways_tenant_provider", "tenant_payment_gateways", type_="unique")
    op.create_unique_constraint("uq_tenant_payment_gateways_tenant", "tenant_payment_gateways", ["tenant_id"])

    op.drop_column("tenant_payment_gateways", "environment")
