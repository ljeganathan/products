"""takeaway qr self-order: section_qr_codes, guest_sessions.section_id/pickup_token

Revision ID: c1d4e8f52a67
Revises: b8e21f6a9c34
Create Date: 2026-09-12 00:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "c1d4e8f52a67"
down_revision = "b8e21f6a9c34"
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
    # One QR per (location, non-seating section) — e.g. Takeaway/Online Delivery.
    # `seating_sections` is tenant-wide, not per-location (a multi-location tenant's
    # "Takeaway" section is one shared row used by every branch), so the QR itself must
    # be keyed on the (location, section) pair, not the section alone — otherwise two
    # branches of the same tenant couldn't have their own separate Takeaway QR. Unlike
    # a table's QR, a scan of this code never joins an existing session — every scan is
    # an independent walk-up order (see guest_sessions changes below).
    op.create_table(
        "section_qr_codes",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("qr_token", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["tenant_locations.id"]),
        sa.ForeignKeyConstraint(["section_id"], ["seating_sections.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("location_id", "section_id", name="uq_section_qr_codes_location_section"),
        sa.UniqueConstraint("qr_token", name="uq_section_qr_codes_qr_token"),
    )
    op.create_index("ix_section_qr_codes_tenant_id_id", "section_qr_codes", ["tenant_id", "id"])
    _enable_rls("section_qr_codes")

    # table_id becomes optional: a Takeaway guest_sessions row has no table at all.
    # Postgres treats every NULL as distinct in a unique index, so the existing
    # uq_guest_sessions_active_table partial index (tenant_id, table_id WHERE
    # status='active') already allows unlimited simultaneous NULL-table_id rows with no
    # change needed — there is deliberately no "at most one active" constraint for
    # Takeaway, since every scan is its own independent order, never a shared cart.
    op.alter_column("guest_sessions", "table_id", nullable=True)
    op.add_column("guest_sessions", sa.Column("section_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_guest_sessions_section_id", "guest_sessions", "seating_sections", ["section_id"], ["id"]
    )
    # The Takeaway guest's own "table number" equivalent — shown instead of a table
    # number (CLAUDE.md §9's table-number-as-dominant-anchor convention, adapted) and
    # used by staff on the KOT Tickets screen to identify which pending order is whose.
    # Assigned once at session creation, per-tenant sequential (e.g. "TA-14"), never for
    # a dine-in session.
    op.add_column("guest_sessions", sa.Column("pickup_token", sa.String(20), nullable=True))
    op.create_check_constraint(
        "ck_guest_sessions_table_or_section",
        "guest_sessions",
        "table_id IS NOT NULL OR section_id IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_guest_sessions_table_or_section", "guest_sessions", type_="check")
    op.drop_column("guest_sessions", "pickup_token")
    op.drop_constraint("fk_guest_sessions_section_id", "guest_sessions", type_="foreignkey")
    op.drop_column("guest_sessions", "section_id")
    op.alter_column("guest_sessions", "table_id", nullable=False)

    _disable_rls("section_qr_codes")
    op.drop_index("ix_section_qr_codes_tenant_id_id", table_name="section_qr_codes")
    op.drop_table("section_qr_codes")
