"""create non-superuser app role

Revision ID: a0b03cc2e4a0
Revises: dd586dfba4be
Create Date: 2026-08-02 14:31:54.205215

The default docker-compose Postgres bootstrap role (`kotmate`, from POSTGRES_USER) is a
superuser — and superusers bypass Row Level Security entirely, regardless of
`FORCE ROW LEVEL SECURITY` (confirmed empirically while writing Phase 01's smoke tests:
RLS silently let an unscoped INSERT through). FORCE only matters for a *non-superuser*
table owner. Migrations keep running as the superuser `kotmate` role (needs DDL rights
and should bypass RLS to seed data without ceremony); the running application connects
as this new, genuinely-unprivileged `kotmate_app` role instead (`app.core.config.
APP_DATABASE_URL`), so RLS actually does something in every environment, not just
production if someone remembers to configure it there.
"""
import os
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a0b03cc2e4a0"
down_revision: Union[str, None] = "dd586dfba4be"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP_ROLE = "kotmate_app"
# Dev-only default, overridable via env var when running this migration somewhere the
# password matters (same convention as the already-committed kotmate/kotmate dev creds).
APP_ROLE_PASSWORD = os.environ.get("APP_DB_PASSWORD", "kotmate_app")


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{APP_ROLE_PASSWORD}'
                    NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
            END IF;
        END
        $$;
        """
    )
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};")
    op.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};")
    # Applies to tables/sequences created by later migrations too, since they always
    # run as the `kotmate` role that issues this ALTER DEFAULT PRIVILEGES statement.
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};"
    )
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE};"
    )


def downgrade() -> None:
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {APP_ROLE};")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {APP_ROLE};")
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROLE};")
    op.execute(f"REVOKE USAGE ON SCHEMA public FROM {APP_ROLE};")
    op.execute(f"DROP ROLE IF EXISTS {APP_ROLE};")
