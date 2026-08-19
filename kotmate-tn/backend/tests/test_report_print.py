"""Tests for the report-print restructure (production feedback round 3, CLAUDE.md
§10/§11): branch header + timestamp on every report, row-wise key-value summaries
(Sales Summary/Tax Summary/Z-Report), renamed/no-"Rs." grid columns for the rest, and
Tamil name rasterization (Item/Category Wise) gated by the tenant's
`report_tamil_names_enabled` toggle.

Two layers:
- Pure renderer tests (`escpos_thermal.render_report`/`dotmatrix_raw.render_report`)
  against hand-built `ReportRenderData` — no DB, fast, exercises exactly what a printer
  would receive.
- HTTP integration tests through `POST /api/v1/reports/print`, covering the
  report_print_service data-shaping (dropped login_id, Tamil toggle, row-wise pairs)
  that the pure renderer tests alone can't catch.
"""

import base64
from datetime import date

import pytest
from httpx import AsyncClient

from app.printing import report_print
from app.printing.base import ReportBody, ReportRenderData
from app.printing.dotmatrix_raw import render_report as render_report_dotmatrix
from app.printing.escpos_thermal import render_report as render_report_thermal

# Only the HTTP integration tests below are async — the pure-renderer tests above them
# call render_report directly and need no event loop, so this mark (applied per-test,
# not module-wide) only decorates the async ones.
_async_test = pytest.mark.asyncio(loop_scope="session")

TODAY = date.today().isoformat()


def _grid_data(**overrides) -> ReportRenderData:
    body = ReportBody(
        kind="grid",
        headers=["Name", "Qty", "Sales"],
        rows=[["Filter Coffee", "2", "50"], ["TOTAL", "", "50"]],
        bold_rows={1},
        big_rows={1},
    )
    defaults = dict(
        title="Item Wise Sales",
        printed_at_label="19-Aug-2026 03:45 PM",
        extra_header_lines=[],
        branch_name="Sri Balaji Hotel",
        branch_address_lines=["Door No 12, Main Street"],
        branch_gstin="33AAAAA0000A1Z5",
        paper_width_mm=58,
        body=body,
    )
    defaults.update(overrides)
    return ReportRenderData(**defaults)


def _keyvalue_data(**overrides) -> ReportRenderData:
    body = ReportBody(
        kind="keyvalue",
        pairs=[("Total Bill Count", "1"), ("Grand Total", "Rs.420"), ("Payment - Cash", "Rs.420")],
    )
    defaults = dict(
        title="Sales Summary",
        printed_at_label="19-Aug-2026 03:45 PM",
        extra_header_lines=[],
        branch_name="Sri Balaji Hotel",
        branch_address_lines=[],
        branch_gstin=None,
        paper_width_mm=58,
        body=body,
    )
    defaults.update(overrides)
    return ReportRenderData(**defaults)


# ---------------------------------------------------------------------------
# report_print.wrap_line
# ---------------------------------------------------------------------------


def test_wrap_line_short_text_unchanged():
    assert report_print.wrap_line("Z Report", 32) == ["Z Report"]


def test_wrap_line_splits_on_word_boundary():
    text = "Shift Close Time: 19-Aug-2026 03:45 PM"
    lines = report_print.wrap_line(text, 32)
    assert all(len(line) <= 32 for line in lines)
    assert " ".join(lines) == text
    assert len(lines) > 1


def test_wrap_line_hard_splits_a_single_word_longer_than_width():
    lines = report_print.wrap_line("Supercalifragilisticexpialidocious", 10)
    assert all(len(line) <= 10 for line in lines)
    assert "".join(lines) == "Supercalifragilisticexpialidocious"


# ---------------------------------------------------------------------------
# Pure renderer tests
# ---------------------------------------------------------------------------


def test_thermal_grid_has_branch_header_and_timestamp():
    out = render_report_thermal(_grid_data())
    assert b"Sri Balaji Hotel" in out
    assert b"Door No 12, Main Street" in out
    assert b"GSTIN: 33AAAAA0000A1Z5" in out
    assert b"19-Aug-2026 03:45 PM" in out
    assert b"Printed:" not in out  # no "Printed:" label prefix, just the date/time


def test_thermal_grid_headers_renamed_and_no_id_columns():
    out = render_report_thermal(_grid_data())
    text = out.decode("utf-8", errors="ignore")
    assert "Name" in text and "Qty" in text and "Sales" in text
    assert "quantity_sold" not in text.lower()
    assert "revenue" not in text.lower()


def test_thermal_grid_total_row_is_bold_and_double_height():
    out = render_report_thermal(_grid_data())
    # ESC E 1 (bold on) and GS ! 0x01 (double-height) must both appear before "TOTAL",
    # and be turned back off afterward — same codes render_bill's Grand Total line uses.
    assert b"\x1bE\x01" in out
    assert b"\x1d!\x01" in out
    assert b"\x1bE\x00" in out
    assert b"\x1d!\x00" in out


def test_thermal_keyvalue_report_is_row_wise_not_one_wide_row():
    out = render_report_thermal(_keyvalue_data())
    lines = out.decode("utf-8", errors="ignore").split("\n")
    bill_count_line = next(line for line in lines if "Total Bill Count" in line)
    grand_total_line = next(line for line in lines if "Grand Total" in line)
    assert bill_count_line != grand_total_line
    assert "Grand Total" not in bill_count_line


def test_thermal_keyvalue_extra_header_lines_print():
    # 80mm/48-col paper — wide enough that neither extra line needs to wrap (word-wrap
    # itself is covered separately below), so this stays a simple presence check.
    data = _keyvalue_data(
        title="Z Report",
        paper_width_mm=80,
        extra_header_lines=[
            "Shift Close Time: 19-Aug-2026 03:45 PM",
            "Closed By: Cashier One (Cashier)",
        ],
    )
    out = render_report_thermal(data)
    assert b"Shift Close Time: 19-Aug-2026 03:45 PM" in out
    assert b"Closed By: Cashier One (Cashier)" in out


def test_thermal_header_line_wraps_on_narrow_paper_instead_of_overflowing():
    # 58mm/32-col paper is too narrow for this 39-char line — it must wrap onto a
    # second line rather than silently overflowing the printer's actual line width.
    data = _keyvalue_data(
        title="Z Report",
        paper_width_mm=58,
        extra_header_lines=["Shift Close Time: 19-Aug-2026 03:45 PM"],
    )
    out = render_report_thermal(data)
    text = out.decode("utf-8", errors="ignore")
    assert "Shift Close Time: 19-Aug-2026 03:45 PM" not in text
    lines = text.split("\n")
    close_time_line = next(line for line in lines if "Shift Close Time:" in line)
    pm_line = next(line for line in lines if "03:45 PM" in line)
    assert close_time_line != pm_line


def test_thermal_grid_tamil_row_rasterizes_and_blanks_text_name():
    body = ReportBody(
        kind="grid",
        headers=["Name", "Qty", "Sales"],
        rows=[["Filter Coffee", "2", "50"], ["TOTAL", "", "50"]],
        bold_rows={1},
        big_rows={1},
        tamil_names={0: "காபி"},
    )
    out = render_report_thermal(_grid_data(body=body))
    # GS v 0 (raster bit-image header: 1D 76 30 00) present — the Tamil name was
    # rasterized, not sent as text.
    assert b"\x1dv0\x00" in out
    # The row's own English name is blanked on its text line once it's been replaced by
    # the rasterized line above it — "Filter Coffee" must not appear as plain text.
    assert b"Filter Coffee" not in out
    # And the raw Tamil UTF-8 bytes never appear as literal text either (that's the
    # original "junk chars" bug this restructure fixes).
    assert "காபி".encode() not in out


def test_thermal_grid_without_tamil_names_shows_plain_english():
    out = render_report_thermal(_grid_data())
    assert b"Filter Coffee" in out


def test_dotmatrix_grid_ignores_tamil_names_always_shows_english():
    # Dot-matrix has no image support at all (CLAUDE.md §10) — tamil_names must be
    # ignored entirely, same accepted limitation dot-matrix bill/KOT already have.
    body = ReportBody(
        kind="grid",
        headers=["Name", "Qty", "Sales"],
        rows=[["Filter Coffee", "2", "50"], ["TOTAL", "", "50"]],
        tamil_names={0: "காபி"},
    )
    out = render_report_dotmatrix(_grid_data(body=body))
    assert "Filter Coffee" in out
    assert "காபி" not in out


def test_dotmatrix_report_has_branch_header_and_form_feed():
    out = render_report_dotmatrix(_grid_data())
    assert "Sri Balaji Hotel" in out
    assert "19-Aug-2026 03:45 PM" in out
    assert out.endswith("\f")


def test_dotmatrix_keyvalue_is_row_wise():
    out = render_report_dotmatrix(_keyvalue_data())
    lines = out.split("\n")
    bill_count_line = next(line for line in lines if "Total Bill Count" in line)
    assert "Grand Total" not in bill_count_line


# ---------------------------------------------------------------------------
# HTTP integration — report_print_service data-shaping
# ---------------------------------------------------------------------------


async def _default_location(client: AsyncClient, headers: dict) -> dict:
    resp = await client.get("/api/v1/locations", headers=headers)
    return resp.json()[0]


async def _enable_report_printing(client: AsyncClient, headers: dict, *, tamil_names: bool = False) -> None:
    resp = await client.patch("/api/v1/settings/report-printing", json={"enabled": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    if tamil_names:
        resp = await client.patch(
            "/api/v1/settings/report-tamil-names", json={"enabled": True}, headers=headers
        )
        assert resp.status_code == 200, resp.text


async def _register_reports_printer(
    client: AsyncClient, headers: dict, location_id: str, *, printer_type: str = "thermal"
) -> dict:
    resp = await client.post(
        "/api/v1/printers",
        json={
            "location_id": location_id,
            "name": "Back Office Reports Printer",
            "target": "reports",
            "printer_type": printer_type,
            "connection_type": "local_agent",
            "connection_details": {"windows_printer_name": "Reports"},
            "paper_width_mm": 58,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _bill_with_named_item(
    client: AsyncClient, headers: dict, location_id: str, name_en: str, name_ta: str | None
) -> None:
    section_resp = await client.get("/api/v1/sections", headers=headers)
    section_id = next(s["id"] for s in section_resp.json() if s["name_en"] == "AC")
    await client.post(
        "/api/v1/tax-rules",
        json={"name": "Standard GST", "cgst_rate": 2.5, "sgst_rate": 2.5, "is_default": True},
        headers=headers,
    )
    category = (
        await client.post("/api/v1/categories", json={"name_en": "Beverages"}, headers=headers)
    ).json()
    item = (
        await client.post(
            "/api/v1/items",
            json={"name_en": name_en, "name_ta": name_ta, "category_id": category["id"], "price": 25},
            headers=headers,
        )
    ).json()
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location_id,
                "section_id": section_id,
                "items": [{"item_id": item["id"], "quantity": 2}],
            },
            headers=headers,
        )
    ).json()
    # price 25 x qty 2 = 50 subtotal; 2.5% CGST + 2.5% SGST = 1.25 + 1.25 = 52.5,
    # round-half-up to the nearest rupee (bill_service._round_half_up_rupee) -> 53.
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 53.0}]},
        headers=headers,
    )
    assert bill.status_code == 201, bill.text


async def _print_report(client: AsyncClient, headers: dict, **payload) -> bytes:
    resp = await client.post("/api/v1/reports/print", json=payload, headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["printed"] is True
    return base64.b64decode(body["print_job"]["data_base64"])


@_async_test
async def test_print_item_wise_shows_english_when_tamil_toggle_off(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers, tamil_names=False)
    await _register_reports_printer(client, headers, location["id"])
    await _bill_with_named_item(client, headers, location["id"], "Filter Coffee", "காபி")

    raw = await _print_report(
        client, headers, report_type="item-wise", date_from=TODAY, date_to=TODAY
    )
    assert b"Filter Coffee" in raw
    assert "காபி".encode() not in raw
    assert b"\x1dv0\x00" not in raw  # no raster block at all — nothing to rasterize
    # Sales column: no "Rs." prefix, always 2 decimal places (2 x 25 = 50.00 exactly).
    assert b"Rs." not in raw
    assert b"50.00" in raw


@_async_test
async def test_print_item_wise_rasterizes_tamil_when_toggle_on(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers, tamil_names=True)
    await _register_reports_printer(client, headers, location["id"])
    await _bill_with_named_item(client, headers, location["id"], "Filter Coffee", "காபி")

    raw = await _print_report(
        client, headers, report_type="item-wise", date_from=TODAY, date_to=TODAY
    )
    assert b"\x1dv0\x00" in raw
    assert b"Filter Coffee" not in raw
    assert "காபி".encode() not in raw


@_async_test
async def test_print_item_wise_dot_matrix_always_english_even_with_toggle_on(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers, tamil_names=True)
    await _register_reports_printer(client, headers, location["id"], printer_type="dotmatrix")
    await _bill_with_named_item(client, headers, location["id"], "Filter Coffee", "காபி")

    raw = await _print_report(
        client, headers, report_type="item-wise", date_from=TODAY, date_to=TODAY
    )
    assert b"Filter Coffee" in raw
    assert "காபி".encode() not in raw


@_async_test
async def test_print_sales_summary_is_row_wise_with_payment_breakdown(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers)
    await _register_reports_printer(client, headers, location["id"])
    await _bill_with_named_item(client, headers, location["id"], "Meals", None)

    raw = await _print_report(
        client, headers, report_type="sales-summary", date_from=TODAY, date_to=TODAY
    )
    text = raw.decode("utf-8", errors="ignore")
    lines = text.split("\n")
    bill_count_line = next(line for line in lines if "Total Bill Count" in line)
    grand_total_line = next(line for line in lines if "Grand Total" in line)
    assert bill_count_line != grand_total_line
    assert b"Payment - Cash" in raw
    assert b"Payment - UPI" in raw
    assert b"Payment - Card" in raw
    assert location["name"].encode() in raw
    # No "Rs." anywhere, no "Printed:" label prefix, and Grand Total (53.0) shows both
    # decimal places — all production feedback round 3.
    assert "Rs." not in text
    assert "Printed:" not in text
    assert "53.00" in grand_total_line


@_async_test
async def test_print_z_report_includes_shift_close_time(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers)
    await _register_reports_printer(client, headers, location["id"])
    await _bill_with_named_item(client, headers, location["id"], "Meals", None)

    raw = await _print_report(client, headers, report_type="z-report", report_date=TODAY)
    assert b"Shift Close Time" in raw
    # tenant_admin closed this shift (conftest.py's onboarding fixture names the admin
    # "Test Admin") — production feedback: "print who logged in either pos/cashier user".
    assert b"Closed By: Test Admin (Admin)" in raw


@_async_test
async def test_print_z_report_closed_by_shows_cashier_when_cashier_prints(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers)
    await _register_reports_printer(client, headers, location["id"])
    await _bill_with_named_item(client, headers, location["id"], "Meals", None)

    cashier_resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "cashier01",
            "name": "Cashier One",
            "role": "pos_user",
            "password": "password123",
        },
        headers=headers,
    )
    assert cashier_resp.status_code == 201, cashier_resp.text
    cashier = cashier_resp.json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": cashier["user_id"], "password": "password123"}
    )
    cashier_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    raw = await _print_report(client, cashier_headers, report_type="z-report", report_date=TODAY)
    assert b"Closed By: Cashier One (Cashier)" in raw


@_async_test
async def test_print_cashier_wise_drops_login_id_keeps_name(
    client: AsyncClient, pro_max_tenant_admin: dict
):
    headers = pro_max_tenant_admin["headers"]
    location = await _default_location(client, headers)
    await _enable_report_printing(client, headers)
    await _register_reports_printer(client, headers, location["id"])

    cashier_resp = await client.post(
        "/api/v1/users",
        json={
            "local_handle": "cashier01",
            "name": "Cashier One",
            "role": "pos_user",
            "password": "password123",
        },
        headers=headers,
    )
    assert cashier_resp.status_code == 201, cashier_resp.text
    cashier = cashier_resp.json()
    login = await client.post(
        "/api/v1/auth/login", json={"user_id": cashier["user_id"], "password": "password123"}
    )
    cashier_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    section_resp = await client.get("/api/v1/sections", headers=headers)
    section_id = next(s["id"] for s in section_resp.json() if s["name_en"] == "AC")
    category = (await client.post("/api/v1/categories", json={"name_en": "Mains"}, headers=headers)).json()
    item = (
        await client.post(
            "/api/v1/items",
            json={"name_en": "Meals", "category_id": category["id"], "price": 200},
            headers=headers,
        )
    ).json()
    order = (
        await client.post(
            "/api/v1/orders",
            json={
                "location_id": location["id"],
                "section_id": section_id,
                "items": [{"item_id": item["id"], "quantity": 1}],
            },
            headers=cashier_headers,
        )
    ).json()
    bill = await client.post(
        "/api/v1/bills",
        json={"order_id": order["id"], "payments": [{"method": "cash", "amount": 200.0}]},
        headers=cashier_headers,
    )
    assert bill.status_code == 201, bill.text

    raw = await _print_report(
        client, headers, report_type="cashier-wise", date_from=TODAY, date_to=TODAY
    )
    text = raw.decode("utf-8", errors="ignore")
    assert "Cashier One" in text
    assert "Cashier Name" in text
    assert cashier["user_id"] not in text
