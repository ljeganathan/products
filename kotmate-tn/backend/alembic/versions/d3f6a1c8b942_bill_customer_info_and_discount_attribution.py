"""bills.customer_name/customer_phone + bill_discounts (per-rule attribution)

Revision ID: d3f6a1c8b942
Revises: c1d4e8f52a67
Create Date: 2026-09-19 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "d3f6a1c8b942"
down_revision = "c1d4e8f52a67"
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
    # Both nullable, no server_default needed — every existing bill simply has neither
    # set (exactly today's behavior) until a new bill captures them. Zero impact on any
    # existing bill/tenant/production data. Phone is stored as free-text (staff can type
    # a landline for a walk-in customer), not digit-normalized here — only the mandatory
    # QR guest-ordering flow (guest_service.py) enforces a strict 10-digit format, since
    # that's the one path this is meant to key future loyalty-point lookups off of.
    op.add_column("bills", sa.Column("customer_name", sa.String(100), nullable=True))
    op.add_column("bills", sa.Column("customer_phone", sa.String(20), nullable=True))

    # The queryable counterpart to bills.discount_note's free-text summary — one row
    # per discount rule that contributed to a bill, so the new Discount Summary/Detail
    # reports can group/sum by rule without parsing that string. discount_rule_id is
    # nullable (a rule could theoretically be removed later) with the name/type
    # snapshotted alongside it, same immutable-reprint precedent as BillItem's own
    # name_en_snapshot/name_ta_snapshot — a renamed or deleted rule never changes how a
    # past bill's own report reads. Only ever written going forward from this
    # migration; existing bills predating it simply have no bill_discounts rows (their
    # discount, if any, still shows correctly on the bill itself via discount_note —
    # they just won't appear broken out by rule in the two new reports).
    op.create_table(
        "bill_discounts",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("bill_id", sa.UUID(), nullable=False),
        sa.Column("discount_rule_id", sa.UUID(), nullable=True),
        sa.Column("rule_name_snapshot", sa.String(100), nullable=False),
        sa.Column("rule_type_snapshot", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bill_id"], ["bills.id"]),
        sa.ForeignKeyConstraint(["discount_rule_id"], ["discount_rules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bill_discounts_tenant_id_id", "bill_discounts", ["tenant_id", "id"])
    _enable_rls("bill_discounts")


def downgrade() -> None:
    _disable_rls("bill_discounts")
    op.drop_index("ix_bill_discounts_tenant_id_id", table_name="bill_discounts")
    op.drop_table("bill_discounts")
    op.drop_column("bills", "customer_phone")
    op.drop_column("bills", "customer_name")
