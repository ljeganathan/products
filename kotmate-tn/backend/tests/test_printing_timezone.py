"""Tests for printing/base.py's IST conversion (production feedback: "all print time
zone is not set to Asia/kolkata current time set this") — KOTMate TN is exclusively for
Tamil Nadu businesses, so every printed timestamp must show India Standard Time
regardless of what timezone the server/container itself runs in. `created_at` columns
are always timezone-aware (db/mixins.py's TimestampMixin, `DateTime(timezone=True)`),
typically stored/returned as UTC — printing one directly via `.strftime()` without
converting first silently shows UTC wall-clock time on the receipt instead.
"""

from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.printing.base import (
    IST,
    BillRenderData,
    KotTicketRenderData,
    format_bill_text_lines,
    format_kot_text_lines,
    now_ist,
    to_ist,
)


def test_to_ist_converts_utc_to_indian_standard_time():
    # 2026-08-19 09:00 UTC -> 2026-08-19 14:30 IST (UTC+5:30).
    utc_dt = datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
    ist_dt = to_ist(utc_dt)
    assert ist_dt.tzinfo == IST
    assert (ist_dt.hour, ist_dt.minute) == (14, 30)
    assert ist_dt.day == 19


def test_to_ist_shifts_across_a_midnight_boundary():
    # 2026-08-19 20:00 UTC -> 2026-08-20 01:30 IST — the date itself changes, which is
    # exactly the kind of bug an unconverted UTC timestamp produces on a printed receipt
    # (wrong day, not just wrong hour) for anything printed late in the UTC evening.
    utc_dt = datetime(2026, 8, 19, 20, 0, tzinfo=UTC)
    ist_dt = to_ist(utc_dt)
    assert ist_dt.day == 20
    assert (ist_dt.hour, ist_dt.minute) == (1, 30)


def test_to_ist_treats_naive_datetime_as_utc_defensively():
    # Every created_at in this codebase is tz-aware in practice — this only guards
    # against astimezone() silently assuming the server's own local zone if one ever
    # isn't (a naive datetime.astimezone() call uses the system timezone by default).
    naive_dt = datetime(2026, 8, 19, 9, 0)  # noqa: DTZ001 — deliberately naive, testing the fallback
    ist_dt = to_ist(naive_dt)
    assert (ist_dt.hour, ist_dt.minute) == (14, 30)


def test_to_ist_is_idempotent_on_an_already_ist_datetime():
    ist_dt = datetime(2026, 8, 19, 14, 30, tzinfo=IST)
    assert to_ist(ist_dt) == ist_dt


def test_to_ist_handles_a_non_utc_source_offset_too():
    # e.g. a hypothetical server running in US/Pacific (UTC-7 in August) rather than
    # UTC — to_ist must convert from *any* source offset, not just assume UTC input.
    pacific = timezone(timedelta(hours=-7))
    dt = datetime(2026, 8, 19, 2, 0, tzinfo=pacific)  # 09:00 UTC -> 14:30 IST
    ist_dt = to_ist(dt)
    assert (ist_dt.day, ist_dt.hour, ist_dt.minute) == (19, 14, 30)


def test_now_ist_returns_tz_aware_datetime_in_kolkata_zone():
    now = now_ist()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=5, minutes=30)


def test_ist_zone_is_asia_kolkata():
    assert IST == ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------------------
# End-to-end through the actual print layout functions — catches a regression if the
# to_ist(...) wrapping at a call site is ever reverted while the helper itself survives.
# ---------------------------------------------------------------------------


def test_kot_ticket_print_shows_ist_not_utc():
    ticket = KotTicketRenderData(
        ticket_number="T-1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime(2026, 8, 19, 20, 0, tzinfo=UTC),  # 01:30 AM IST next day
        lines=[],
    )
    lines = format_kot_text_lines(ticket)
    assert "20-Aug-2026 01:30 AM" in lines
    assert "19-Aug-2026 08:00 PM" not in lines


def test_bill_print_shows_ist_not_utc():
    bill = BillRenderData(
        bill_number="B-1",
        table_number="T5",
        section_name_en="AC",
        created_at=datetime(2026, 8, 19, 9, 0, tzinfo=UTC),  # 02:30 PM IST same day
        lines=[],
        subtotal=100.0,
        discount_amount=0.0,
        discount_note=None,
        cgst_amount=2.5,
        sgst_amount=2.5,
        round_off_amount=0.0,
        grand_total=105.0,
        payments=[("cash", 105.0)],
        hotel_name="Test Hotel",
        hotel_address_lines=[],
        gstin=None,
        upi_id=None,
        qr_payload=None,
        show_tamil_names=True,
    )
    lines = format_bill_text_lines(bill)
    joined = "\n".join(lines)
    assert "02:30 PM" in joined
    assert "09:00 AM" not in joined
