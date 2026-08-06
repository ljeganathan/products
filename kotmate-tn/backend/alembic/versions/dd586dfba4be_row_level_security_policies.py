"""row level security policies

Revision ID: dd586dfba4be
Revises: f4960432d454
Create Date: 2026-08-02 14:26:09.225515

Defense-in-depth (CLAUDE.md §4) on top of the app's own `WHERE tenant_id = ...`
filtering: every tenant-scoped table gets an RLS policy gated by two session vars the
API layer sets per request (Phase 02):
  - `app.current_tenant_id` — set by `require_tenant_scope` for tenant-scoped requests.
  - `app.is_platform_admin` — set to 'true' by `require_platform_scope` for
    `product_owner` endpoints that need cross-tenant visibility.
Neither var set (the default on any connection that skips both dependencies) means the
policy evaluates to false and no rows are visible — fails closed, not open.

`FORCE ROW LEVEL SECURITY` matters here because the app DB role is also the table owner
(it ran the migrations) — table owners bypass RLS by default in Postgres, which would
silently defeat this policy entirely without FORCE.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "dd586dfba4be"
down_revision: Union[str, None] = "f4960432d454"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table carrying a tenant_id column. `tenants`, `plans`, and `roles` are
# deliberately excluded — they're platform-level tables with no tenant_id column.
TENANT_SCOPED_TABLES = [
    "tenant_locations",
    "subscriptions",
    "users",
    "user_location_access",
    "categories",
    "items",
    "seating_sections",
    "item_section_prices",
    "waiters",
    "tables",
    "orders",
    "order_items",
    "kot_tickets",
    "kot_ticket_items",
    "bills",
    "bill_items",
    "payments",
    "tax_rules",
    "discount_rules",
    "printers",
    "hotel_master",
    "audit_log",
]

_POLICY_EXPR = (
    "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid "
    "OR current_setting('app.is_platform_admin', true) = 'true'"
)


def upgrade() -> None:
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING ({_POLICY_EXPR})
            WITH CHECK ({_POLICY_EXPR});
            """
        )


def downgrade() -> None:
    for table in TENANT_SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
