"""Shared enums/constants used by both models (CHECK constraints) and seed migrations.

Plain Python lists + Postgres CHECK constraints are used instead of native Postgres
ENUM types throughout this schema: adding/renaming a value later is a simple data
migration instead of an ALTER TYPE dance (relevant for INDIAN_STATES especially,
since Indian state/UT boundaries have changed within living memory).
"""

INDIAN_STATES = [
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Sikkim",
    "Tamil Nadu",
    "Telangana",
    "Tripura",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Andaman and Nicobar Islands",
    "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu",
    "Delhi",
    "Jammu and Kashmir",
    "Ladakh",
    "Lakshadweep",
    "Puducherry",
]

# GSTIN's first 2 digits are the numeric state/UT code (e.g. 33 = Tamil Nadu).
# Used to cross-validate hotel_master.state against hotel_master.gstin (Phase 10).
GST_STATE_CODES = {
    "01": "Jammu and Kashmir",
    "02": "Himachal Pradesh",
    "03": "Punjab",
    "04": "Chandigarh",
    "05": "Uttarakhand",
    "06": "Haryana",
    "07": "Delhi",
    "08": "Rajasthan",
    "09": "Uttar Pradesh",
    "10": "Bihar",
    "11": "Sikkim",
    "12": "Arunachal Pradesh",
    "13": "Nagaland",
    "14": "Manipur",
    "15": "Mizoram",
    "16": "Tripura",
    "17": "Meghalaya",
    "18": "Assam",
    "19": "West Bengal",
    "20": "Jharkhand",
    "21": "Odisha",
    "22": "Chhattisgarh",
    "23": "Madhya Pradesh",
    "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu",
    "27": "Maharashtra",
    "29": "Karnataka",
    "30": "Goa",
    "31": "Lakshadweep",
    "32": "Kerala",
    "33": "Tamil Nadu",
    "34": "Puducherry",
    "35": "Andaman and Nicobar Islands",
    "36": "Telangana",
    "37": "Andhra Pradesh",
    "38": "Ladakh",
}

ROLE_CODES = ["product_owner", "tenant_admin", "pos_user", "waiter", "kitchen"]

# Roles a tenant_admin can assign in User Management (Phase 04) — product_owner is
# platform-only and never appears here. "kitchen" is labeled "KOT User" in all UI copy
# (CLAUDE.md §5) but keeps its backend role code for RLS/API continuity.
TENANT_STAFF_ROLE_CODES = ["tenant_admin", "pos_user", "waiter", "kitchen"]

# Roles counted against plans.max_users (CLAUDE.md §6: "Users (Admin + POS)") — waiter
# and kitchen seats are uncapped by the seat limit.
BILLABLE_ROLE_CODES = ["tenant_admin", "pos_user"]

PLAN_CODES = ["lite", "pro", "pro_max"]

ORDER_STATUSES = ["open", "held", "billed"]
TABLE_STATUSES = ["free", "occupied", "billed"]
KOT_TICKET_STATUSES = ["new", "preparing", "ready"]
PRINTER_TARGETS = ["kot", "bill"]
PRINTER_TYPES = ["thermal", "dotmatrix"]
PRINTER_CONNECTION_TYPES = ["network", "usb", "local_agent"]
DISCOUNT_TYPES = ["flat_percent", "item_level", "coupon"]
PAYMENT_METHODS = ["upi", "cash", "card"]
BILL_STATUSES = ["finalized", "void"]
SUBSCRIPTION_STATUSES = ["active", "suspended", "cancelled"]
BILLING_CYCLES = ["monthly", "yearly"]
PAYMENT_STATUSES = ["paid", "pending", "overdue"]
