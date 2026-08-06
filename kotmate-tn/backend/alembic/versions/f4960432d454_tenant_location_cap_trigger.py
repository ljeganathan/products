"""tenant location cap trigger

Revision ID: f4960432d454
Revises: a20112fa8ba8
Create Date: 2026-08-02 14:26:08.253476

DB-level defense-in-depth (CLAUDE.md §4/§6) enforcing `count(active tenant_locations)
<= plan.max_locations` (Lite=1, Pro=2, Pro Max=5), mirroring the service-layer seat-cap
pattern from Phase 04 but backstopped here in case application code ever skips the check.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4960432d454"
down_revision: Union[str, None] = "a20112fa8ba8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION enforce_tenant_location_cap() RETURNS TRIGGER AS $$
        DECLARE
            v_max_locations INTEGER;
            v_active_count INTEGER;
        BEGIN
            IF NEW.is_active IS DISTINCT FROM TRUE THEN
                RETURN NEW;
            END IF;

            SELECT p.max_locations INTO v_max_locations
            FROM subscriptions s
            JOIN plans p ON p.id = s.plan_id
            WHERE s.tenant_id = NEW.tenant_id AND s.status = 'active'
            ORDER BY s.created_at DESC
            LIMIT 1;

            -- No resolvable active subscription: the service layer is expected to never
            -- create a tenant_location before a subscription exists, so we don't block here.
            IF v_max_locations IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT count(*) INTO v_active_count
            FROM tenant_locations
            WHERE tenant_id = NEW.tenant_id AND is_active = TRUE AND id <> NEW.id;

            IF v_active_count >= v_max_locations THEN
                RAISE EXCEPTION
                    'tenant_location cap of % reached for tenant %', v_max_locations, NEW.tenant_id
                    USING ERRCODE = 'check_violation';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_enforce_tenant_location_cap
        BEFORE INSERT OR UPDATE OF is_active, tenant_id ON tenant_locations
        FOR EACH ROW
        EXECUTE FUNCTION enforce_tenant_location_cap();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_enforce_tenant_location_cap ON tenant_locations;")
    op.execute("DROP FUNCTION IF EXISTS enforce_tenant_location_cap();")
