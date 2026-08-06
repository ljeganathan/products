"""tenant code and global unique user id

Revision ID: 3d908345eda4
Revises: a0b03cc2e4a0
Create Date: 2026-08-02 17:19:38.721164

Phase 02 (CLAUDE.md §5): login is a single `user_id` field with no separate
tenant/company selector, but `user_id` was previously only unique *per tenant* — two
tenants could collide on the same login id, leaving login unable to tell them apart.
Fix: give every tenant a short unique `tenant_code` (assigned in Phase 03) and make
`users.user_id` globally unique, composed at creation (Phase 04) as
`{tenant_code}-{local_handle}` for tenant-scoped roles. product_owner keeps a bare,
unprefixed user_id.

Autogenerate doesn't detect CHECK constraints, so the format checks on both new/changed
columns are hand-added below.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d908345eda4'
down_revision: Union[str, None] = 'a0b03cc2e4a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable first so existing rows (if any) can be backfilled before NOT NULL.
    op.add_column('tenants', sa.Column('tenant_code', sa.String(length=10), nullable=True))
    op.execute(
        "UPDATE tenants SET tenant_code = 'T' || LPAD(sub.rn::text, 5, '0') "
        "FROM (SELECT id, row_number() OVER (ORDER BY created_at) AS rn FROM tenants) sub "
        "WHERE tenants.id = sub.id AND tenants.tenant_code IS NULL"
    )
    op.alter_column('tenants', 'tenant_code', existing_type=sa.String(length=10), nullable=False)
    op.create_unique_constraint(op.f('uq_tenants_tenant_code'), 'tenants', ['tenant_code'])
    op.create_check_constraint(
        'ck_tenants_tenant_code_format', 'tenants', "tenant_code ~ '^[A-Z0-9]{2,10}$'"
    )

    op.alter_column('users', 'user_id',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=60),
               existing_nullable=False)
    op.drop_index('uq_users_tenant_id_user_id', table_name='users', postgresql_where='(tenant_id IS NOT NULL)')
    op.drop_index('uq_users_user_id_platform', table_name='users', postgresql_where='(tenant_id IS NULL)')
    op.create_unique_constraint(op.f('uq_users_user_id'), 'users', ['user_id'])
    op.create_check_constraint(
        'ck_users_user_id_format', 'users', "user_id ~ '^[A-Za-z0-9_-]{2,60}$'"
    )


def downgrade() -> None:
    op.drop_constraint('ck_users_user_id_format', 'users', type_='check')
    op.drop_constraint(op.f('uq_users_user_id'), 'users', type_='unique')
    op.create_index('uq_users_user_id_platform', 'users', ['user_id'], unique=True, postgresql_where='(tenant_id IS NULL)')
    op.create_index('uq_users_tenant_id_user_id', 'users', ['tenant_id', 'user_id'], unique=True, postgresql_where='(tenant_id IS NOT NULL)')
    op.alter_column('users', 'user_id',
               existing_type=sa.String(length=60),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)

    op.drop_constraint('ck_tenants_tenant_code_format', 'tenants', type_='check')
    op.drop_constraint(op.f('uq_tenants_tenant_code'), 'tenants', type_='unique')
    op.drop_column('tenants', 'tenant_code')
