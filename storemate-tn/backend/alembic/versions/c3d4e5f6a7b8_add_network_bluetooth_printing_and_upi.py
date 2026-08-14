"""add network/bluetooth/rawbt printer connections, connection_details, and UPI QR fields

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New connection types alongside the existing webusb/local_agent, mirroring
    # the printing architecture already shipped in KOTMate TN (CLAUDE.md printing
    # section): network/WiFi (direct raw-socket, backend-side), Web Bluetooth
    # (browser BLE GATT, no server round-trip), and RawBT (Android app bridge).
    op.execute("ALTER TYPE printer_connection ADD VALUE IF NOT EXISTS 'network'")
    op.execute("ALTER TYPE printer_connection ADD VALUE IF NOT EXISTS 'wifi'")
    op.execute("ALTER TYPE printer_connection ADD VALUE IF NOT EXISTS 'bluetooth'")
    op.execute("ALTER TYPE printer_connection ADD VALUE IF NOT EXISTS 'rawbt'")

    op.add_column(
        'printer_profiles',
        sa.Column('connection_details', JSONB(), nullable=False, server_default='{}'),
    )

    op.add_column('company_settings', sa.Column('upi_vpa', sa.String(length=100), nullable=True))
    op.add_column(
        'company_settings',
        sa.Column('show_upi_qr', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('company_settings', 'show_upi_qr')
    op.drop_column('company_settings', 'upi_vpa')
    op.drop_column('printer_profiles', 'connection_details')
    # Postgres has no ALTER TYPE ... DROP VALUE — the added enum labels are left
    # in place on downgrade (harmless: nothing writes them once this migration
    # is reverted).
