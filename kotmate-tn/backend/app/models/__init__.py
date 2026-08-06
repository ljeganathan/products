"""Importing this package registers every model on Base.metadata — required before
Alembic autogenerate or app startup touches the metadata.
"""

from app.models.audit import AuditLog
from app.models.bill import Bill, BillItem, Payment
from app.models.category import Category
from app.models.discount import DiscountRule
from app.models.hotel import HotelMaster
from app.models.item import Item
from app.models.kot import KotTicket, KotTicketItem
from app.models.order import Order, OrderItem
from app.models.plan import Plan, Subscription
from app.models.platform_settings import PlatformSettings
from app.models.printer import Printer
from app.models.section import ItemSectionPrice, SeatingSection
from app.models.table import Table
from app.models.tax import TaxRule
from app.models.tenant import Tenant, TenantLocation
from app.models.user import Role, User, UserLocationAccess
from app.models.waiter import Waiter

__all__ = [
    "AuditLog",
    "Bill",
    "BillItem",
    "Payment",
    "Category",
    "DiscountRule",
    "HotelMaster",
    "Item",
    "KotTicket",
    "KotTicketItem",
    "Order",
    "OrderItem",
    "Plan",
    "Subscription",
    "PlatformSettings",
    "Printer",
    "ItemSectionPrice",
    "SeatingSection",
    "Table",
    "TaxRule",
    "Tenant",
    "TenantLocation",
    "Role",
    "User",
    "UserLocationAccess",
    "Waiter",
]
