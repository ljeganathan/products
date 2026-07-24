"""Seed dev/demo data: one tenant, the 3 plans, 3 users, categories, ~15 FMCG
items with starter stock. Safe to re-run — skips work that already exists.

Usage: python scripts/seed_dev_data.py
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from passlib.context import CryptContext  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.category import Category  # noqa: E402
from app.models.enums import (  # noqa: E402
    ItemUnit,
    LanguagePref,
    PlanCode,
    SubscriptionStatus,
    TenantStatus,
    UserRole,
)
from app.models.item import Item  # noqa: E402
from app.models.plan import Plan  # noqa: E402
from app.models.stock import Stock  # noqa: E402
from app.models.store import Store  # noqa: E402
from app.models.subscription import Subscription  # noqa: E402
from app.models.tax_profile import TaxProfile  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.models.user import User  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PLAN_DEFS = [
    {
        "code": PlanCode.LITE,
        "name": "Lite",
        "price_paise": 79_900,
        "max_users": 2,
        "max_stores": 1,
        "max_printer_profiles": 1,
        "low_stock_alerts": False,
        "saved_bill_days": 7,
        "features_json": {
            "low_stock_alerts": False,
            "multi_store": False,
            "dashboard_range": False,
            "discount_rules_advanced": False,
            "api_access": False,
        },
    },
    {
        "code": PlanCode.PRO,
        "name": "Pro",
        "price_paise": 199_900,
        "max_users": 5,
        "max_stores": 1,
        "max_printer_profiles": 3,
        "low_stock_alerts": True,
        "saved_bill_days": 90,
        "features_json": {
            "low_stock_alerts": True,
            "multi_store": False,
            "dashboard_range": True,
            "discount_rules_advanced": True,
            "api_access": False,
        },
    },
    {
        "code": PlanCode.PRO_MAX,
        "name": "Pro Max",
        "price_paise": 399_900,
        "max_users": -1,
        "max_stores": -1,
        "max_printer_profiles": -1,
        "low_stock_alerts": True,
        "saved_bill_days": -1,
        "features_json": {
            "low_stock_alerts": True,
            "multi_store": True,
            "dashboard_range": True,
            "discount_rules_advanced": True,
            "api_access": True,
        },
    },
]

CATEGORY_DEFS = [
    {"key": "groceries", "name_en": "Groceries", "name_ta": "மளிகைப் பொருட்கள்"},
    {"key": "snacks", "name_en": "Snacks", "name_ta": "தின்பண்டங்கள்"},
    {"key": "beverages", "name_en": "Beverages", "name_ta": "பானங்கள்"},
    {"key": "dairy", "name_en": "Dairy", "name_ta": "பால் பொருட்கள்"},
    {"key": "personal_care", "name_en": "Personal Care", "name_ta": "தனிப்பட்ட பராமரிப்பு"},
]

TAX_PROFILE_DEFS = [
    {"key": "exempt", "name": "Exempt", "cgst_pct": 0, "sgst_pct": 0, "igst_pct": 0, "is_default": True},
    {"key": "gst_5", "name": "GST 5%", "cgst_pct": 2.5, "sgst_pct": 2.5, "igst_pct": 5},
    {"key": "gst_12", "name": "GST 12%", "cgst_pct": 6, "sgst_pct": 6, "igst_pct": 12},
    {"key": "gst_18", "name": "GST 18%", "cgst_pct": 9, "sgst_pct": 9, "igst_pct": 18},
]

# (category_key, tax_key, name_en, name_ta, brand, pack_size, unit, mrp, selling, cost,
#  hsn_code, reorder_level, reorder_qty, stock_qty, batch_tracked)
ITEM_DEFS = [
    ("groceries", "exempt", "Ponni Rice 5kg", "பொன்னி அரிசி 5கிலோ", "Local", "5kg",
     ItemUnit.KG, 30000, 29000, 26000, "1006", 10, 20, 50, False),
    ("groceries", "gst_5", "Toor Dal 1kg", "துவரம் பருப்பு 1கிலோ", "Local", "1kg",
     ItemUnit.KG, 16000, 15500, 14000, "0713", 8, 15, 40, False),
    ("groceries", "gst_5", "Sunflower Oil 1L", "சூரியகாந்தி எண்ணெய் 1லிட்டர்", "Gold Winner", "1L",
     ItemUnit.L, 18000, 17500, 16000, "1512", 6, 12, 30, False),
    ("groceries", "gst_5", "Sugar 1kg", "சர்க்கரை 1கிலோ", "Local", "1kg",
     ItemUnit.KG, 4800, 4600, 4200, "1701", 10, 20, 60, False),
    ("groceries", "exempt", "Salt 1kg", "உப்பு 1கிலோ", "Tata Salt", "1kg",
     ItemUnit.KG, 2200, 2000, 1700, "2501", 15, 30, 80, False),
    ("snacks", "gst_18", "Parle-G Biscuits 200g", "பார்லே-ஜி பிஸ்கட் 200கி", "Parle", "200g",
     ItemUnit.PACK, 3000, 2800, 2400, "1905", 20, 40, 100, False),
    ("snacks", "gst_18", "Good Day Biscuits 150g", "குட் டே பிஸ்கட் 150கி", "Britannia", "150g",
     ItemUnit.PACK, 3500, 3300, 2800, "1905", 15, 30, 80, False),
    ("snacks", "gst_12", "Haldiram Namkeen 200g", "ஆல்டிராம் நம்கீன் 200கி", "Haldiram's", "200g",
     ItemUnit.PACK, 6000, 5800, 5000, "2106", 8, 16, 40, False),
    ("beverages", "gst_5", "Tata Tea Gold 250g", "டாட்டா டீ கோல்ட் 250கி", "Tata", "250g",
     ItemUnit.PACK, 14000, 13500, 12000, "0902", 6, 12, 35, False),
    ("beverages", "gst_5", "Nescafe Coffee 50g", "நெஸ்கஃபே காபி 50கி", "Nestle", "50g",
     ItemUnit.PACK, 16500, 16000, 14500, "2101", 5, 10, 25, False),
    ("dairy", "exempt", "Amul Milk 500ml", "அமுல் பால் 500மிலி", "Amul", "500ml",
     ItemUnit.ML, 2700, 2700, 2400, "0401", 20, 40, 60, True),
    ("dairy", "gst_12", "Amul Ghee 500ml", "அமுல் நெய் 500மிலி", "Amul", "500ml",
     ItemUnit.ML, 32000, 31000, 28500, "0405", 4, 8, 20, False),
    ("personal_care", "gst_18", "Lux Soap 100g", "லக்ஸ் சோப்பு 100கி", "Lux", "100g",
     ItemUnit.PCS, 4000, 3800, 3200, "3401", 18, 36, 90, False),
    ("personal_care", "gst_18", "Clinic Plus Shampoo 175ml", "கிளினிக் பிளஸ் ஷாம்பு 175மிலி",
     "Clinic Plus", "175ml", ItemUnit.ML, 9500, 9200, 8000, "3305", 9, 18, 45, False),
    ("personal_care", "gst_18", "Colgate Toothpaste 100g", "கோல்கேட் பற்பசை 100கி", "Colgate",
     "100g", ItemUnit.PCS, 5500, 5200, 4500, "3306", 11, 22, 55, False),
]

DEMO_TENANT_NAME = "Demo Store Chennai"
DEMO_OWNER_EMAIL = "owner@demostorechennai.in"


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing_tenant = await db.scalar(select(Tenant).where(Tenant.name == DEMO_TENANT_NAME))
        if existing_tenant is not None:
            print(f"Demo tenant '{DEMO_TENANT_NAME}' already exists — skipping seed.")
            return

        # --- plans (idempotent lookup by code) ---
        plans: dict[PlanCode, Plan] = {}
        for plan_def in PLAN_DEFS:
            plan = await db.scalar(select(Plan).where(Plan.code == plan_def["code"]))
            if plan is None:
                plan = Plan(**plan_def)
                db.add(plan)
                await db.flush()
            plans[plan_def["code"]] = plan

        # --- tenant + store ---
        tenant = Tenant(
            name=DEMO_TENANT_NAME,
            owner_email=DEMO_OWNER_EMAIL,
            owner_phone="+919840000001",
            status=TenantStatus.ACTIVE,
        )
        db.add(tenant)
        await db.flush()

        store = Store(
            tenant_id=tenant.id,
            name="Demo Store Chennai - Main",
            address="12, Anna Salai, Chennai, Tamil Nadu 600002",
            gstin="33AAAAA0000A1Z5",
            phone="+914400000001",
            is_default=True,
        )
        db.add(store)
        await db.flush()

        now = datetime.now(timezone.utc)
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plans[PlanCode.PRO].id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )
        db.add(subscription)

        # --- users ---
        db.add_all(
            [
                User(
                    tenant_id=None,
                    store_id=None,
                    name="Platform Owner",
                    email="owner@storematetn.in",
                    phone="+919840000000",
                    password_hash=pwd_context.hash("Owner@123"),
                    role=UserRole.PRODUCT_OWNER,
                    language_pref=LanguagePref.EN,
                ),
                User(
                    tenant_id=tenant.id,
                    store_id=store.id,
                    name="Admin User",
                    email="admin@demostorechennai.in",
                    phone="+919840000002",
                    password_hash=pwd_context.hash("Admin@123"),
                    role=UserRole.ADMIN,
                    language_pref=LanguagePref.EN,
                ),
                User(
                    tenant_id=tenant.id,
                    store_id=store.id,
                    name="Cashier User",
                    email="cashier@demostorechennai.in",
                    phone="+919840000003",
                    password_hash=pwd_context.hash("Cashier@123"),
                    role=UserRole.POS_USER,
                    language_pref=LanguagePref.TA,
                ),
            ]
        )

        # --- tax profiles ---
        tax_profiles: dict[str, TaxProfile] = {}
        for tax_def in TAX_PROFILE_DEFS:
            key = tax_def.pop("key")
            tax_profile = TaxProfile(tenant_id=tenant.id, **tax_def)
            db.add(tax_profile)
            tax_profiles[key] = tax_profile
        await db.flush()

        # --- categories ---
        categories: dict[str, Category] = {}
        for cat_def in CATEGORY_DEFS:
            key = cat_def["key"]
            category = Category(
                tenant_id=tenant.id, name_en=cat_def["name_en"], name_ta=cat_def["name_ta"]
            )
            db.add(category)
            categories[key] = category
        await db.flush()

        # --- items + starter stock ---
        for idx, (
            cat_key,
            tax_key,
            name_en,
            name_ta,
            brand,
            pack_size,
            unit,
            mrp,
            selling,
            cost,
            hsn_code,
            reorder_level,
            reorder_qty,
            stock_qty,
            batch_tracked,
        ) in enumerate(ITEM_DEFS, start=1):
            item = Item(
                tenant_id=tenant.id,
                store_id=store.id,
                category_id=categories[cat_key].id,
                name_en=name_en,
                name_ta=name_ta,
                sku=f"SKU-{idx:04d}",
                barcode=f"89000000{idx:04d}",
                unit=unit,
                mrp_paise=mrp,
                selling_price_paise=selling,
                cost_price_paise=cost,
                tax_profile_id=tax_profiles[tax_key].id,
                reorder_level=reorder_level,
                reorder_qty=reorder_qty,
                brand=brand,
                pack_size=pack_size,
                hsn_code=hsn_code,
                batch_tracked=batch_tracked,
            )
            db.add(item)
            await db.flush()

            db.add(
                Stock(
                    tenant_id=tenant.id,
                    store_id=store.id,
                    item_id=item.id,
                    quantity_on_hand=stock_qty,
                    last_restocked_at=now,
                )
            )

        await db.commit()

        print(f"Seeded tenant '{DEMO_TENANT_NAME}' ({tenant.id})")
        print(f"  store: {store.name} ({store.id})")
        print(f"  plans: {', '.join(p.code.value for p in plans.values())}")
        print("  users: owner@storematetn.in / Owner@123 (product_owner)")
        print("         admin@demostorechennai.in / Admin@123 (admin)")
        print("         cashier@demostorechennai.in / Cashier@123 (pos_user)")
        print(f"  categories: {len(CATEGORY_DEFS)}, tax profiles: {len(TAX_PROFILE_DEFS)}")
        print(f"  items + stock: {len(ITEM_DEFS)}")


if __name__ == "__main__":
    asyncio.run(seed())
