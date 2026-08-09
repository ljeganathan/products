"""Reusable manual-testing data seeder — one demo hotel per subscription tier.

Run from `backend/`:  python -m scripts.seed_demo_data

Idempotent by natural key (company name, item code, table number, login handle, ...):
re-running tops up rather than duplicates, so it's safe to run repeatedly — e.g. once
per manual-testing session to guarantee fresh "today" bills for Reports/Dashboard
(Phase 11), or after a fresh dev DB restore. Every login's password is reset to
DEMO_PASSWORD on every run, so credentials never go stale even if changed by hand
during testing.

Creates, per tier (CLAUDE.md §6/§7):
  Lite Demo Hotel      — 1 location, no item images, no KOT printer, flat_percent-only
                          discount, single tax rate.
  Pro Demo Hotel       — 1 location, item images, KOT + Bill printers, flat_percent +
                          item-level discounts.
  Pro Max Demo Hotel   — 2 locations (for multi-location dashboard/reports testing),
                          item images, KOT + Bill printers at both locations, a coupon
                          code, per-item tax override support.

Each tenant gets: Hotel Master (logo/GSTIN/UPI), 2 categories, 5 items, 1 default tax
rule, 2 tables, 1 waiter (2% incentive, with its own waiter-role login) + 1 cashier (1%
incentive), and a handful of finalized bills for today (plus one backdated to
yesterday) so date-range filters have something to filter.

Uses the superuser `DATABASE_URL` (bypasses RLS entirely — the same tool-script
pattern as scripts/create_superuser.py), so no `set_config` RLS dance is needed here.
"""

import asyncio
import io
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.deps import CurrentUser  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import (  # noqa: E402
    Bill,
    Category,
    DiscountRule,
    Item,
    Printer,
    Role,
    Table,
    TaxRule,
    Tenant,
    TenantLocation,
    User,
    Waiter,
)
from app.schemas.bills import (  # noqa: E402
    BillCreateRequest,
    BillPaymentInput,
    BillPreviewRequest,
)
from app.schemas.categories import CategoryCreateRequest  # noqa: E402
from app.schemas.discounts import DiscountRuleCreateRequest  # noqa: E402
from app.schemas.hotel_master import HotelMasterUpdateRequest  # noqa: E402
from app.schemas.items import ItemCreateRequest  # noqa: E402
from app.schemas.locations import LocationCreateRequest  # noqa: E402
from app.schemas.orders import OrderCreateRequest, OrderLineInput  # noqa: E402
from app.schemas.platform import TenantCreateRequest  # noqa: E402
from app.schemas.printers import PrinterCreateRequest  # noqa: E402
from app.schemas.tables import TableCreateRequest  # noqa: E402
from app.schemas.tax_rules import TaxRuleCreateRequest  # noqa: E402
from app.schemas.users import UserCreateRequest  # noqa: E402
from app.schemas.waiters import WaiterCreateRequest  # noqa: E402
from app.services.bill_service import finalize_bill, preview_bill  # noqa: E402
from app.services.category_service import create_category  # noqa: E402
from app.services.discount_rule_service import create_discount_rule  # noqa: E402
from app.services.hotel_master_service import upsert_hotel_master  # noqa: E402
from app.services.item_service import create_item  # noqa: E402
from app.services.location_service import create_location  # noqa: E402
from app.services.order_service import create_order  # noqa: E402
from app.services.printer_service import create_printer  # noqa: E402
from app.services.storage import get_storage  # noqa: E402
from app.services.table_service import create_table  # noqa: E402
from app.services.tax_rule_service import create_tax_rule  # noqa: E402
from app.services.tenant_onboarding import onboard_tenant  # noqa: E402
from app.services.user_management import create_user  # noqa: E402
from app.services.waiter_service import create_waiter  # noqa: E402

DEMO_PASSWORD = "Demo@12345"

PLAN_HOTELS = [
    ("lite", "Lite Demo Hotel"),
    ("pro", "Pro Demo Hotel"),
    ("pro_max", "Pro Max Demo Hotel"),
]

ITEM_DEFS = [
    # name_en, name_ta, price, item_code, image color
    ("Meals", "சாப்பாடு", 150, "101", (196, 132, 41)),
    ("Filter Coffee", "காபி", 30, "102", (94, 61, 38)),
    ("Chicken Biryani", "சிக்கன் பிரியாணி", 220, "103", (168, 42, 30)),
    ("Masala Dosa", "மசாலா தோசை", 90, "104", (222, 184, 84)),
    ("Gulab Jamun", "குலாப் ஜாமுன்", 60, "105", (156, 39, 78)),
]


def _placeholder_image(label: str, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (400, 300), color=color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 389, 289], outline="white", width=4)
    draw.text((30, 140), label, fill="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


async def _get_admin(session: AsyncSession, tenant_id: uuid.UUID) -> User:
    return (
        await session.execute(
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(User.tenant_id == tenant_id, Role.code == "tenant_admin")
        )
    ).scalars().first()


async def get_or_create_tenant(session: AsyncSession, plan_code: str, company_name: str) -> Tenant:
    tenant = (
        await session.execute(select(Tenant).where(Tenant.company_name == company_name))
    ).scalar_one_or_none()
    if tenant is not None:
        admin = await _get_admin(session, tenant.id)
        admin.password_hash = hash_password(DEMO_PASSWORD)
        await session.flush()
        return tenant

    req = TenantCreateRequest(
        company_name=company_name,
        door_no="12",
        street="Anna Salai",
        city="Chennai",
        district="Chennai",
        state="Tamil Nadu",
        pincode="600002",
        plan_code=plan_code,
        billing_cycle="monthly",
        location_name=f"{company_name} - Main",
        admin_local_handle="admin",
        admin_name="Demo Admin",
        admin_password=DEMO_PASSWORD,
    )
    tenant = await onboard_tenant(session, req)
    await session.commit()
    return tenant


async def get_or_create_location(
    session: AsyncSession, tenant_id: uuid.UUID, name: str, **overrides
) -> TenantLocation:
    loc = (
        await session.execute(
            select(TenantLocation).where(
                TenantLocation.tenant_id == tenant_id, TenantLocation.name == name
            )
        )
    ).scalar_one_or_none()
    if loc is not None:
        return loc
    payload = {"name": name, "state": "Tamil Nadu", "pincode": "600003", "city": "Chennai"}
    payload.update(overrides)
    loc = await create_location(session, tenant_id, LocationCreateRequest(**payload))
    await session.commit()
    return loc


async def get_or_create_category(session: AsyncSession, tenant_id: uuid.UUID, name_en: str) -> Category:
    cat = (
        await session.execute(
            select(Category).where(Category.tenant_id == tenant_id, Category.name_en == name_en)
        )
    ).scalar_one_or_none()
    if cat is not None:
        return cat
    cat = await create_category(session, tenant_id, CategoryCreateRequest(name_en=name_en))
    await session.commit()
    return cat


async def get_or_create_item(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    category_id: uuid.UUID,
    name_en: str,
    name_ta: str,
    price: float,
    item_code: str,
    with_image: bool,
    image_color: tuple[int, int, int],
) -> Item:
    item = (
        await session.execute(
            select(Item).where(Item.tenant_id == tenant_id, Item.item_code == item_code)
        )
    ).scalar_one_or_none()
    if item is None:
        item = await create_item(
            session,
            tenant_id,
            ItemCreateRequest(
                name_en=name_en,
                name_ta=name_ta,
                category_id=category_id,
                price=price,
                item_code=item_code,
            ),
        )
        await session.commit()

    if with_image and item.image_url is None:
        storage = get_storage()
        url = await storage.save(
            tenant_id=tenant_id,
            subfolder="items",
            filename=f"{item_code}.png",
            content=_placeholder_image(name_en, image_color),
        )
        item.image_url = url
        await session.commit()
    return item


async def get_or_create_tax_rule(session: AsyncSession, tenant_id: uuid.UUID) -> TaxRule:
    rule = (
        await session.execute(
            select(TaxRule).where(TaxRule.tenant_id == tenant_id, TaxRule.name == "Standard GST")
        )
    ).scalar_one_or_none()
    if rule is not None:
        return rule
    rule = await create_tax_rule(
        session,
        tenant_id,
        TaxRuleCreateRequest(name="Standard GST", cgst_rate=2.5, sgst_rate=2.5, is_default=True),
    )
    await session.commit()
    return rule


async def get_or_create_printer(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID, target: str
) -> Printer:
    printer = (
        await session.execute(
            select(Printer).where(
                Printer.tenant_id == tenant_id, Printer.location_id == location_id, Printer.target == target
            )
        )
    ).scalar_one_or_none()
    if printer is not None:
        return printer
    name = "Kitchen Printer" if target == "kot" else "Counter Bill Printer"
    printer = await create_printer(
        session,
        tenant_id,
        PrinterCreateRequest(
            location_id=location_id,
            name=name,
            target=target,
            printer_type="thermal",
            connection_type="network",
        ),
    )
    await session.commit()
    return printer


async def get_or_create_discount_rule(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    rule_type: str,
    value: float,
    coupon_code: str | None,
) -> DiscountRule:
    rule = (
        await session.execute(
            select(DiscountRule).where(DiscountRule.tenant_id == tenant_id, DiscountRule.name == name)
        )
    ).scalar_one_or_none()
    if rule is not None:
        return rule
    rule = await create_discount_rule(
        session,
        tenant_id,
        DiscountRuleCreateRequest(name=name, type=rule_type, value=value, coupon_code=coupon_code),
    )
    await session.commit()
    return rule


async def get_or_create_table(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    section_id: uuid.UUID,
    table_number: str,
) -> Table:
    tbl = (
        await session.execute(
            select(Table).where(
                Table.tenant_id == tenant_id,
                Table.location_id == location_id,
                Table.table_number == table_number,
            )
        )
    ).scalar_one_or_none()
    if tbl is not None:
        return tbl
    tbl = await create_table(
        session,
        tenant_id,
        TableCreateRequest(
            location_id=location_id,
            section_id=section_id,
            table_number=table_number,
            seating_capacity=4,
        ),
    )
    await session.commit()
    return tbl


async def get_or_create_staff_login(
    session: AsyncSession,
    tenant: Tenant,
    local_handle: str,
    name: str,
    role: str,
    incentive_rate: float | None,
) -> User:
    login_id = f"{tenant.tenant_code}{local_handle}"
    user = (await session.execute(select(User).where(User.user_id == login_id))).scalar_one_or_none()
    if user is not None:
        user.password_hash = hash_password(DEMO_PASSWORD)
        await session.commit()
        return user
    resp = await create_user(
        session,
        tenant,
        UserCreateRequest(
            local_handle=local_handle,
            name=name,
            role=role,
            password=DEMO_PASSWORD,
            incentive_rate=incentive_rate,
        ),
    )
    await session.commit()
    return (await session.execute(select(User).where(User.id == resp.id))).scalar_one()


async def get_or_create_waiter(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
    waiter_number: str,
    name: str,
    incentive_rate: float,
    user_id: uuid.UUID | None,
) -> Waiter:
    w = (
        await session.execute(
            select(Waiter).where(Waiter.tenant_id == tenant_id, Waiter.waiter_number == waiter_number)
        )
    ).scalar_one_or_none()
    if w is not None:
        return w
    w = await create_waiter(
        session,
        tenant_id,
        WaiterCreateRequest(
            location_id=location_id,
            waiter_number=waiter_number,
            name=name,
            incentive_rate=incentive_rate,
            user_id=user_id,
        ),
    )
    await session.commit()
    return w


async def _bill_order(
    session: AsyncSession,
    tenant: Tenant,
    location_id: uuid.UUID,
    section_id: uuid.UUID,
    cashier: User,
    waiter_id: uuid.UUID | None,
    lines: list[OrderLineInput],
    payment_methods: list[str],
    coupon_code: str | None,
    backdate_days: int = 0,
) -> Bill:
    current_user = CurrentUser(
        id=cashier.id, login_id=cashier.user_id, role="pos_user", tenant_id=tenant.id, location_ids=[]
    )
    order = await create_order(
        session,
        tenant.id,
        current_user,
        OrderCreateRequest(
            location_id=location_id, section_id=section_id, waiter_id=waiter_id, items=lines
        ),
    )
    await session.commit()

    preview = await preview_bill(
        session, tenant.id, BillPreviewRequest(order_id=order.id, coupon_code=coupon_code)
    )
    grand_total = preview.grand_total
    if len(payment_methods) == 1:
        payments = [BillPaymentInput(method=payment_methods[0], amount=grand_total)]
    else:
        split = round(grand_total / len(payment_methods), 2)
        last_amount = round(grand_total - split * (len(payment_methods) - 1), 2)
        payments = [BillPaymentInput(method=m, amount=split) for m in payment_methods[:-1]]
        payments.append(BillPaymentInput(method=payment_methods[-1], amount=last_amount))

    result = await finalize_bill(
        session,
        tenant.id,
        current_user,
        BillCreateRequest(order_id=order.id, coupon_code=coupon_code, payments=payments),
    )
    await session.commit()

    if backdate_days:
        await session.execute(
            text("UPDATE bills SET created_at = created_at - make_interval(days => :d) WHERE id = :id"),
            {"d": backdate_days, "id": str(result.id)},
        )
        await session.commit()
    return (await session.execute(select(Bill).where(Bill.id == result.id))).scalar_one()


async def ensure_todays_bills(
    session: AsyncSession,
    tenant: Tenant,
    location_id: uuid.UUID,
    section_id: uuid.UUID,
    items: list[Item],
    cashier: User,
    waiter: Waiter,
    plan_code: str,
    discount_rule: DiscountRule | None,
) -> int:
    today_count = (
        await session.execute(
            text(
                "SELECT count(*) FROM bills WHERE tenant_id = :tid AND location_id = :lid "
                "AND created_at >= :today AND created_at < :tomorrow"
            ),
            {
                "tid": str(tenant.id),
                "lid": str(location_id),
                "today": date.today(),
                "tomorrow": date.today() + timedelta(days=1),
            },
        )
    ).scalar_one()
    if today_count >= 4:
        return 0

    meals, coffee, biryani, dosa, jamun = items
    created = 0

    await _bill_order(
        session, tenant, location_id, section_id, cashier, waiter.id,
        [OrderLineInput(item_id=meals.id, quantity=2), OrderLineInput(item_id=coffee.id, quantity=2)],
        ["cash"], None,
    )
    created += 1

    await _bill_order(
        session, tenant, location_id, section_id, cashier, None,
        [OrderLineInput(item_id=biryani.id, quantity=1)],
        ["upi"], None,
    )
    created += 1

    # No explicit discount object needed here anymore — the "Festival Offer" flat rule
    # created in seed_tenant() is active with no expiry, so it auto-applies to every
    # bill on its own (Phase 23).
    await _bill_order(
        session, tenant, location_id, section_id, cashier, waiter.id,
        [OrderLineInput(item_id=dosa.id, quantity=2), OrderLineInput(item_id=jamun.id, quantity=1)],
        ["card"], None,
    )
    created += 1

    if plan_code == "pro_max" and discount_rule is not None:
        await _bill_order(
            session, tenant, location_id, section_id, cashier, waiter.id,
            [OrderLineInput(item_id=meals.id, quantity=1), OrderLineInput(item_id=biryani.id, quantity=1)],
            ["cash", "upi"], discount_rule.coupon_code,
        )
    else:
        await _bill_order(
            session, tenant, location_id, section_id, cashier, None,
            [OrderLineInput(item_id=coffee.id, quantity=3)],
            ["upi"], None,
        )
    created += 1

    # One bill backdated to yesterday so a report date-range picker has something to
    # actually filter (all the ones above are "today" by construction).
    await _bill_order(
        session, tenant, location_id, section_id, cashier, waiter.id,
        [OrderLineInput(item_id=meals.id, quantity=1)],
        ["cash"], None, backdate_days=1,
    )
    created += 1

    return created


async def seed_tenant(session: AsyncSession, plan_code: str, company_name: str) -> dict:
    tenant = await get_or_create_tenant(session, plan_code, company_name)
    admin = await _get_admin(session, tenant.id)
    location = await get_or_create_location(session, tenant.id, f"{company_name} - Main")

    await upsert_hotel_master(
        session,
        tenant.id,
        HotelMasterUpdateRequest(
            location_id=location.id,
            name=company_name,
            door_no="12",
            street="Anna Salai",
            city="Chennai",
            district="Chennai",
            state="Tamil Nadu",
            pincode="600002",
            phone="9840000000",
            gstin="33ABCDE1234F1Z5",
            upi_id=f"{company_name.lower().replace(' ', '')}@upi",
            show_tamil_names=True,
        ),
    )
    storage = get_storage()
    logo_url = await storage.save(
        tenant_id=tenant.id, subfolder="hotel", filename="logo.png",
        content=_placeholder_image(company_name.split()[0], (31, 111, 78)),
    )
    hotel = (
        await session.execute(
            text("SELECT id FROM hotel_master WHERE location_id = :lid"), {"lid": str(location.id)}
        )
    ).scalar_one()
    await session.execute(
        text("UPDATE hotel_master SET logo_url = :url WHERE id = :id"),
        {"url": logo_url, "id": str(hotel)},
    )
    await session.commit()

    sections = (
        await session.execute(
            text("SELECT id, name_en FROM seating_sections WHERE tenant_id = :tid"),
            {"tid": str(tenant.id)},
        )
    ).all()
    ac_section_id = next(uuid.UUID(str(sid)) for sid, name in sections if name == "AC")

    category = await get_or_create_category(session, tenant.id, "Mains")
    with_images = plan_code in ("pro", "pro_max")
    items = [
        await get_or_create_item(
            session, tenant.id, category.id, name_en, name_ta, price, code, with_images, color
        )
        for name_en, name_ta, price, code, color in ITEM_DEFS
    ]

    await get_or_create_tax_rule(session, tenant.id)
    await get_or_create_printer(session, tenant.id, location.id, "bill")
    if plan_code in ("pro", "pro_max"):
        await get_or_create_printer(session, tenant.id, location.id, "kot")

    await get_or_create_discount_rule(session, tenant.id, "Festival Offer", "flat_percent", 10, None)
    coupon_rule = None
    if plan_code == "pro_max":
        coupon_rule = await get_or_create_discount_rule(
            session, tenant.id, "Welcome Coupon", "coupon", 10, "WELCOME10"
        )

    table1 = await get_or_create_table(session, tenant.id, location.id, ac_section_id, "T1")
    await get_or_create_table(session, tenant.id, location.id, ac_section_id, "T2")

    waiter_login = await get_or_create_staff_login(
        session, tenant, "waiter01", "Ravi Kumar", "waiter", None
    )
    waiter = await get_or_create_waiter(
        session, tenant.id, location.id, "W1", "Ravi Kumar", 2.0, waiter_login.id
    )
    cashier = await get_or_create_staff_login(
        session, tenant, "cashier01", "Meena Devi", "pos_user", 1.0
    )

    bills_created = await ensure_todays_bills(
        session, tenant, location.id, ac_section_id, items, cashier, waiter, plan_code, coupon_rule
    )

    result = {
        "company_name": company_name,
        "plan_code": plan_code,
        "tenant_code": tenant.tenant_code,
        "admin_login": admin.user_id,
        "cashier_login": cashier.user_id,
        "waiter_login": waiter_login.user_id,
        "table": table1.table_number,
        "location": location.name,
        "bills_created_this_run": bills_created,
    }

    if plan_code == "pro_max":
        branch2 = await get_or_create_location(
            session, tenant.id, f"{company_name} - Branch Two", pincode="600004"
        )
        await get_or_create_printer(session, tenant.id, branch2.id, "bill")
        b2_table = await get_or_create_table(session, tenant.id, branch2.id, ac_section_id, "T1")
        b2_count = (
            await session.execute(
                text(
                    "SELECT count(*) FROM bills WHERE tenant_id = :tid AND location_id = :lid "
                    "AND created_at >= :today"
                ),
                {"tid": str(tenant.id), "lid": str(branch2.id), "today": date.today()},
            )
        ).scalar_one()
        if b2_count == 0:
            await _bill_order(
                session, tenant, branch2.id, ac_section_id, admin, None,
                [OrderLineInput(item_id=items[0].id, quantity=1)],
                ["upi"], None,
            )
        result["branch2_location"] = branch2.name
        result["branch2_table"] = b2_table.table_number

    return result


async def main() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    summaries = []
    try:
        async with session_maker() as session:
            for plan_code, company_name in PLAN_HOTELS:
                summary = await seed_tenant(session, plan_code, company_name)
                summaries.append(summary)
    finally:
        await engine.dispose()

    print("\n" + "=" * 78)
    print("DEMO DATA READY — all passwords:", DEMO_PASSWORD)
    print("=" * 78)
    for s in summaries:
        print(f"\n{s['company_name']} ({s['plan_code'].upper()}, tenant_code={s['tenant_code']})")
        print(f"  Admin login    : {s['admin_login']}")
        print(f"  Cashier login  : {s['cashier_login']}")
        print(f"  Waiter login   : {s['waiter_login']}")
        print(f"  Location/Table : {s['location']} / {s['table']}")
        if "branch2_location" in s:
            print(f"  Branch 2       : {s['branch2_location']} / {s['branch2_table']}")
        print(f"  Bills created this run: {s['bills_created_this_run']} (skipped if already >=4 for today)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
