"""seed plans and roles

Revision ID: a20112fa8ba8
Revises: 5cadf97c7c21
Create Date: 2026-08-02 14:25:30.884112

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a20112fa8ba8"
down_revision: Union[str, None] = "5cadf97c7c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Ad-hoc table definitions (not the ORM models) so this migration's shape is frozen in
# time and stays correct even if app.models.Plan/Role are edited later.
plans_table = sa.table(
    "plans",
    sa.column("id", PgUUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("max_users", sa.Integer),
    sa.column("max_locations", sa.Integer),
    sa.column("price_monthly", sa.Numeric),
    sa.column("price_yearly", sa.Numeric),
    sa.column("features", JSONB),
    sa.column("is_active", sa.Boolean),
)

roles_table = sa.table(
    "roles",
    sa.column("id", PgUUID(as_uuid=True)),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
)

PLANS = [
    {
        "code": "lite",
        "name": "Lite",
        "max_users": 2,
        "max_locations": 1,
        "price_monthly": 999,
        "price_yearly": 9990,
        "features": {
            "item_images": False,
            "section_pricing": False,
            "top_selling_images": False,
            "kot_printing": False,
            "tax_mode": "single_rate",
            "discount_types": ["flat_percent"],
            "qr_upi": False,
            "reports": "basic",
            "export_formats": [],
            "item_import": False,
            "item_export": False,
            "kds": False,
            "priority_support": False,
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "max_users": 6,
        "max_locations": 2,
        "price_monthly": 2499,
        "price_yearly": 24990,
        "features": {
            "item_images": True,
            "section_pricing": True,
            "top_selling_images": True,
            "kot_printing": True,
            "tax_mode": "multi_rate",
            "discount_types": ["flat_percent", "item_level"],
            "qr_upi": True,
            "reports": "charts_csv",
            "export_formats": ["csv"],
            "item_import": False,
            "item_export": True,
            "kds": True,
            "priority_support": False,
        },
    },
    {
        "code": "pro_max",
        "name": "Pro Max",
        "max_users": None,
        "max_locations": 5,
        "price_monthly": 4999,
        "price_yearly": 49990,
        "features": {
            "item_images": True,
            "section_pricing": True,
            "top_selling_images": True,
            "kot_printing": True,
            "tax_mode": "multi_rate_per_item",
            "discount_types": ["flat_percent", "item_level", "coupon"],
            "qr_upi": True,
            "reports": "charts_csv_pdf_excel_multilocation",
            "export_formats": ["csv", "pdf", "excel"],
            "item_import": True,
            "item_export": True,
            "kds": True,
            "priority_support": True,
        },
    },
]

ROLES = [
    {"code": "product_owner", "name": "Product Owner"},
    {"code": "tenant_admin", "name": "Tenant Admin"},
    {"code": "pos_user", "name": "Cashier"},
    {"code": "waiter", "name": "Waiter"},
    {"code": "kitchen", "name": "Kitchen"},
]


def upgrade() -> None:
    op.bulk_insert(
        plans_table,
        [{"id": uuid.uuid4(), "is_active": True, **plan} for plan in PLANS],
    )
    op.bulk_insert(
        roles_table,
        [{"id": uuid.uuid4(), **role} for role in ROLES],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM plans WHERE code IN ('lite', 'pro', 'pro_max')"))
    op.execute(
        sa.text(
            "DELETE FROM roles WHERE code IN "
            "('product_owner', 'tenant_admin', 'pos_user', 'waiter', 'kitchen')"
        )
    )
