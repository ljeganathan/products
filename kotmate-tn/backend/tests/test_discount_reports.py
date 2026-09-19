"""Phase 27 — bill customer name/phone, per-rule discount attribution, and the
Discount Summary / Discount Detail reports.
"""

from datetime import date

import pytest
from httpx import AsyncClient

from app.schemas.reports import DiscountDetailRow
from app.services.report_print_service import discount_detail_export_grid, discount_detail_print_body
from tests.test_bills import (
    _create_category,
    _create_discount_rule,
    _create_item,
    _create_order,
    _default_location_id,
    _section_id,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

TODAY = date.today().isoformat()


async def _bill(client, headers, price, customer=None):
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers, name_en=f"C{price}")
    item = await _create_item(client, headers, category["id"], name_en=f"I{price}", price=price)
    lines = [{"item_id": item["id"], "quantity": 1}]
    order = await _create_order(client, headers, location_id, section_id, lines)
    preview_resp = await client.post("/api/v1/bills/preview", json={"order_id": order["id"]}, headers=headers)
    preview = preview_resp.json()
    payload = {
        "order_id": order["id"],
        "payments": [{"method": "cash", "amount": preview["grand_total"]}],
        **(customer or {}),
    }
    resp = await client.post("/api/v1/bills", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_customer_on_bill_and_discount_reports(client: AsyncClient, tenant_admin: dict):
    headers = tenant_admin["headers"]
    await _create_discount_rule(client, headers, name="Festival Offer", value=10)

    named = await _bill(client, headers, 200, {"customer_name": " Ravi ", "customer_phone": "9876543210"})
    plain = await _bill(client, headers, 100)
    assert named["customer_name"] == "Ravi"
    assert named["customer_phone"] == "9876543210"
    assert plain["customer_name"] is None

    params = {"date_from": TODAY, "date_to": TODAY}
    summary = (await client.get("/api/v1/reports/discount-summary", params=params, headers=headers)).json()
    assert [r["discount_name"] for r in summary["rows"]] == ["Festival Offer"]
    row = summary["rows"][0]
    assert row["discount_amount"] == 30.0
    # Sales matches Sales Summary's grand total (already net of discount); Total Bill is
    # the pre-discount amount.
    assert row["sales_after_discount"] == named["grand_total"] + plain["grand_total"]
    assert row["total_bill_amount"] == round(row["sales_after_discount"] + 30.0, 2)

    detail = (await client.get("/api/v1/reports/discount-detail", params=params, headers=headers)).json()
    assert len(detail["rows"]) == 2
    by_bill = {r["bill_number"]: r for r in detail["rows"]}
    assert by_bill[named["bill_number"]]["customer_name"] == "Ravi"
    assert by_bill[plain["bill_number"]]["customer_phone"] is None
    assert detail["total_discount_amount"] == 30.0


@pytest.mark.filterwarnings("ignore::pytest.PytestWarning")
def test_discount_detail_print_puts_contact_on_second_line():
    rows = [
        DiscountDetailRow(
            discount_name="Offer", bill_number="B1", customer_name="Ravi", customer_phone="98",
            total_bill_amount=100, discount_amount=10, sales_after_discount=90,
        ),
        DiscountDetailRow(
            discount_name="Offer", bill_number="B2", customer_name=None, customer_phone=None,
            total_bill_amount=50, discount_amount=5, sales_after_discount=45,
        ),
    ]
    body = discount_detail_print_body(rows, 150, 15, 135)
    assert [r[0] for r in body.rows] == ["Offer", "B1", "  Ravi / 98", "B2", "TOTAL"]
    headers, grid = discount_detail_export_grid(rows, 150, 15, 135)
    assert len(headers) == 7 and grid[0][2:4] == ["Ravi", "98"]


async def test_two_stacked_rules_and_fully_discounted_zero_total_bill(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    """Item-level + flat + coupon can stack until the bill is ₹0 — it must still
    finalize (a ₹0 payment row), and both rules appear in the discount report.
    """
    headers = pro_max_tenant_admin["headers"]
    location_id = await _default_location_id(client, headers)
    section_id = await _section_id(client, headers, "AC")
    category = await _create_category(client, headers)
    item = await _create_item(client, headers, category["id"], price=90)
    await _create_discount_rule(client, headers, name="Festival", value=10)
    await _create_discount_rule(
        client, headers, name="Free", type="coupon", coupon_code="FREE100", value=100
    )
    order = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    preview = await client.post(
        "/api/v1/bills/preview", json={"order_id": order["id"], "coupon_code": "FREE100"}, headers=headers
    )
    assert preview.json()["grand_total"] == 0

    resp = await client.post(
        "/api/v1/bills",
        json={
            "order_id": order["id"],
            "coupon_code": "FREE100",
            "payments": [{"method": "cash", "amount": 0}],
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text

    params = {"date_from": TODAY, "date_to": TODAY}
    summary = (await client.get("/api/v1/reports/discount-summary", params=params, headers=headers)).json()
    assert {r["discount_name"] for r in summary["rows"]} == {"Festival", "Free"}

    # A zero payment is still rejected when the bill actually has a balance.
    order2 = await _create_order(
        client, headers, location_id, section_id, [{"item_id": item["id"], "quantity": 1}]
    )
    bad = await client.post(
        "/api/v1/bills", json={"order_id": order2["id"], "payments": [{"method": "cash", "amount": 0}]},
        headers=headers,
    )
    assert bad.status_code == 400
