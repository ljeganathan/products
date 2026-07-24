import enum


class PlanCode(str, enum.Enum):
    LITE = "lite"
    PRO = "pro"
    PRO_MAX = "pro_max"


class TenantStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    VOID = "void"


class UserRole(str, enum.Enum):
    PRODUCT_OWNER = "product_owner"
    ADMIN = "admin"
    POS_USER = "pos_user"


class LanguagePref(str, enum.Enum):
    EN = "en"
    TA = "ta"


class ItemUnit(str, enum.Enum):
    PCS = "pcs"
    KG = "kg"
    G = "g"
    L = "l"
    ML = "ml"
    BOX = "box"
    PACK = "pack"


class StockMovementReason(str, enum.Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"


class DiscountScope(str, enum.Enum):
    ITEM = "item"
    CATEGORY = "category"
    BILL = "bill"


class DiscountType(str, enum.Enum):
    FLAT = "flat"
    PERCENT = "percent"


class PaymentMode(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    SPLIT = "split"


class BillStatus(str, enum.Enum):
    COMPLETED = "completed"
    HELD = "held"
    CANCELLED = "cancelled"


class PrinterType(str, enum.Enum):
    THERMAL_58MM = "thermal_58mm"
    THERMAL_80MM = "thermal_80mm"
    DOT_MATRIX = "dot_matrix"


class PrinterConnection(str, enum.Enum):
    WEBUSB = "webusb"
    LOCAL_AGENT = "local_agent"


class NotificationType(str, enum.Enum):
    LOW_STOCK = "low_stock"
    SUBSCRIPTION = "subscription"
    SYSTEM = "system"
