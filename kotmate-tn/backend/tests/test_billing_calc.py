"""Pure-function unit tests for Phase 09 billing math — no DB/client fixture needed.
Covers round-off (CLAUDE.md's own worked example: ₹247.60 -> ₹248.00, round_off=+0.40),
Indian digit-grouping formatting, and the ESC/POS QR raster structure.
"""

from datetime import datetime

from app.printing.base import (
    BillLine,
    BillRenderData,
    KotTicketLine,
    KotTicketRenderData,
    format_bill_text_lines,
    format_inr,
    format_kot_text_lines,
)
from app.printing.qr import generate_qr_escpos
from app.services.bill_service import _round_half_up_rupee


def test_round_half_up_matches_claude_md_worked_example():
    # CLAUDE.md §9: "e.g. ₹247.60 → ₹248.00 grand total with round_off_amount = +0.40"
    pre_round_total = 247.60
    grand_total = float(_round_half_up_rupee(pre_round_total))
    round_off = round(grand_total - pre_round_total, 2)
    assert grand_total == 248.0
    assert round_off == 0.40


def test_round_half_up_rounds_down_below_half():
    assert _round_half_up_rupee(247.40) == 247


def test_round_half_up_exact_half_rounds_up_not_banker():
    # Python's builtin round() would give 248 (already even) for .5 here too, but 247.5
    # is the case that actually distinguishes round-half-up from round-half-to-even —
    # round(0.5) == 0 and round(1.5) == 2 under banker's rounding, so use a value where
    # the built-in would go the wrong way.
    assert _round_half_up_rupee(246.50) == 247
    assert round(246.50) == 246  # confirms builtin round() would silently under-round


def test_format_inr_lakh_grouping():
    assert format_inr(125000) == "₹1,25,000"


def test_format_inr_hides_paise_when_zero():
    assert format_inr(120) == "₹120"


def test_format_inr_shows_paise_when_nonzero():
    assert format_inr(120.5) == "₹120.50"


def test_qr_escpos_bytes_structurally_valid():
    """Validates the actual generated image bytes (GS v 0 raster command), not just that
    generation didn't crash — CLAUDE.md Phase 09 acceptance criteria.
    """
    payload = "upi://pay?pa=hotel@upi&pn=Test+Hotel&am=248.00&cu=INR&tn=Bill%20B1"
    data = generate_qr_escpos(payload, box_size=3)

    assert data[:3] == b"\x1dv0"  # GS v 0 command
    assert data[3] == 0  # mode byte (normal)

    width_bytes = data[4] | (data[5] << 8)
    height = data[6] | (data[7] << 8)
    assert width_bytes > 0
    assert height > 0
    # height is a multiple of box_size since every QR module is scaled uniformly.
    assert height % 3 == 0

    expected_len = 8 + width_bytes * height
    assert len(data) == expected_len


def test_qr_escpos_bytes_change_with_payload():
    a = generate_qr_escpos("upi://pay?pa=a@upi&am=10.00")
    b = generate_qr_escpos("upi://pay?pa=b@upi&am=999.00")
    assert a != b


# --- Phase 10: hotel_master.show_tamil_names gates printed KOT/bill only ---


def test_kot_formatter_hides_tamil_when_toggled_off():
    ticket = KotTicketRenderData(
        ticket_number="T1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
        lines=[KotTicketLine(name_en="Meals", name_ta="சாப்பாடு", quantity=1)],
        show_tamil_names=False,
    )
    lines = format_kot_text_lines(ticket)
    assert not any("சாப்பாடு" in line for line in lines)
    assert any("Meals" in line for line in lines)


def test_kot_formatter_shows_tamil_when_toggled_on():
    ticket = KotTicketRenderData(
        ticket_number="T1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
        lines=[KotTicketLine(name_en="Meals", name_ta="சாப்பாடு", quantity=1)],
        show_tamil_names=True,
    )
    lines = format_kot_text_lines(ticket)
    assert any("சாப்பாடு" in line for line in lines)


def test_bill_formatter_hides_tamil_when_toggled_off():
    bill = BillRenderData(
        bill_number="B1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
        lines=[BillLine(name_en="Meals", name_ta="சாப்பாடு", quantity=1, unit_price=100.0, line_total=100.0)],
        subtotal=100.0,
        discount_amount=0,
        cgst_amount=0,
        sgst_amount=0,
        round_off_amount=0,
        grand_total=100.0,
        payments=[],
        hotel_name="Test Hotel",
        hotel_address_lines=[],
        gstin=None,
        upi_id=None,
        qr_payload=None,
        show_tamil_names=False,
    )
    lines = format_bill_text_lines(bill)
    assert not any("சாப்பாடு" in line for line in lines)


# --- Phase 21: party_label ("Customer-N") composed into the printed header ---


def test_kot_header_label_includes_party_label_when_present():
    ticket = KotTicketRenderData(
        ticket_number="T1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
        party_label="Customer-2",
    )
    assert ticket.header_label == "T5 Customer-2 (AC)"


def test_kot_header_label_omits_party_label_when_absent():
    # Non-seating sections, or any order predating this feature — format matches the
    # pre-Phase-21 output exactly.
    ticket = KotTicketRenderData(
        ticket_number="T1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
    )
    assert ticket.header_label == "T5 (AC)"


def test_bill_header_label_includes_party_label_when_present():
    bill = BillRenderData(
        bill_number="B1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime.now(),
        lines=[],
        subtotal=100.0,
        discount_amount=0,
        cgst_amount=0,
        sgst_amount=0,
        round_off_amount=0,
        grand_total=100.0,
        payments=[],
        hotel_name="Test Hotel",
        hotel_address_lines=[],
        gstin=None,
        upi_id=None,
        qr_payload=None,
        show_tamil_names=True,
        party_label="Customer-2",
    )
    assert bill.header_label == "T5 Customer-2 (AC)"
