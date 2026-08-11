from datetime import datetime

from app.printing.base import (
    _PAYMENT_LABELS,
    BillRenderData,
    KotTicketRenderData,
    format_inr,
    line_chars_for_paper_width,
    two_column_lines,
)
from app.printing.qr import generate_qr_escpos
from app.printing.raster import render_logo_to_escpos
from app.printing.tamil_raster import render_tamil_text_to_escpos

_ESC = b"\x1b"
_GS = b"\x1d"
_INIT = _ESC + b"@"
_BOLD_ON = _ESC + b"E\x01"
_BOLD_OFF = _ESC + b"E\x00"
_CUT = _ESC + b"i"
_CENTER = _ESC + b"a\x01"
_LEFT = _ESC + b"a\x00"
_LINE_SPACING_TIGHT = _ESC + b"3" + bytes([0])
_LINE_SPACING_DEFAULT = _ESC + b"2"
# GS ! n — character size: bits 0-3 = height multiplier - 1, bits 4-7 = width
# multiplier - 1. 0x11 = double height + double width, 0x01 = double height only,
# 0x00 = normal. Double-height-only keeps the fixed-width label/amount column math
# valid (double-width would make a line overflow the printable area), so the
# Grand Total line uses 0x01 while the (short, standalone, centered) hotel-name
# fallback can afford full double size.
_SIZE_NORMAL = _GS + b"!" + bytes([0x00])
_SIZE_DOUBLE = _GS + b"!" + bytes([0x11])
_SIZE_DOUBLE_HEIGHT = _GS + b"!" + bytes([0x01])
# Roughly matches a 58mm/32-col printer's ~12 dots-per-character Font A metrics, and
# holds for 80mm/48-col too (both presets are 12px/char by construction in
# printing/base.py's line_chars_for_paper_width) — used to size raster images
# (Tamil names, logo) proportionally to the printer's actual line width instead of a
# fixed 58mm assumption.
_PX_PER_CHAR = 12


def _text(s: str) -> bytes:
    return s.encode("utf-8") + b"\n"


def _tamil_line(name_ta: str, max_width_px: int) -> bytes:
    """Indented raster line for a Tamil item name — thermal printer firmware has no
    Tamil glyphs in its built-in font, so this rasterizes it as a small bitmap image
    instead of sending it as (unprintable) text, the same technique already used for
    the UPI QR code below. See printing/tamil_raster.py.

    Wrapped in ESC 3 0 / ESC 2 (tight line spacing, then restore default): several
    common thermal firmwares add the printer's *default* line spacing (~1/6") on top
    of the raster image's own height when the following LF is processed, which reads
    as several blank lines after every Tamil name. Zeroing spacing just for this image
    means the line feed after it advances only by the image's actual pixel height.
    """
    return (
        _LINE_SPACING_TIGHT
        + render_tamil_text_to_escpos(name_ta, max_width_px=max_width_px)
        + b"\n"
        + _LINE_SPACING_DEFAULT
    )


def render_test_print(paper_width_mm: int | None) -> bytes:
    """A short, self-contained ticket for the Printers settings page's "Test Print"
    button — proves the registered connection actually reaches the physical printer
    before a real bill/KOT ticket depends on it, independent of any tenant data.
    """
    line_width = line_chars_for_paper_width(paper_width_mm)
    sep = _text("-" * line_width)
    out = _INIT + _CENTER + _BOLD_ON + _SIZE_DOUBLE
    out += _text("KOTMate TN")
    out += _SIZE_NORMAL
    out += _text("Test Print")
    out += _BOLD_OFF
    out += sep
    out += _text("If you can read this,")
    out += _text("the printer is set up correctly.")
    out += sep
    out += _text(datetime.now().strftime("%d-%b-%Y %I:%M %p"))
    out += _LEFT
    return out + b"\n\n" + _CUT


def render_kot(ticket: KotTicketRenderData) -> bytes:
    """ESC/POS byte stream for a thermal KOT printer (Pro/Pro Max, CLAUDE.md §10) —
    big/bold/centered ticket number (kitchen staff call out and track tickets by this
    number, same "dominant element" treatment as the table number on a bill, CLAUDE.md
    §9), plain item lines, partial cut at the end. English item names print as plain
    text; Tamil names (when `show_tamil_names`) print as a rasterized line right below,
    since the printer's own font has no Tamil glyphs.
    """
    sep = _text("-" * ticket.line_width)
    max_width_px = ticket.line_width * _PX_PER_CHAR

    out = _INIT + _CENTER + _BOLD_ON + _SIZE_DOUBLE
    out += _text(f"KOT #{ticket.ticket_number}")
    out += _SIZE_NORMAL + _BOLD_OFF + _LEFT
    out += _text(ticket.header_label)
    out += _text(ticket.created_at.strftime("%d-%b-%Y %I:%M %p"))
    out += sep
    for line in ticket.lines:
        out += _text(f"{line.quantity} x {line.name_en}")
        if ticket.show_tamil_names and line.name_ta:
            out += _tamil_line(line.name_ta, max_width_px)
        if line.notes:
            out += _text(f"    ({line.notes})")
    out += sep
    return out + b"\n\n" + _CUT


def render_bill(bill: BillRenderData) -> bytes:
    """ESC/POS byte stream for a thermal bill printer — bill printing is available on
    every plan tier (CLAUDE.md §6), unlike KOT physical printing which is Pro/Pro Max
    only. The header is either the hotel's logo (rasterized from `logo_image_bytes`,
    already read from disk by the caller) or, when there's no logo, the hotel name
    printed large/bold/centered instead — a logo image may already have the name baked
    into its artwork, so both aren't printed together. The UPI QR (when
    `bill.qr_payload` is set — gated by the `qr_upi` plan feature and a configured
    `hotel_master.upi_id`) is embedded as a centered raster image; Tamil item names are
    rasterized the same way (no Tamil glyphs in the printer's built-in font — see
    printing/tamil_raster.py). Amounts print with "Rs." rather than the ₹ glyph, which
    also isn't in the printer's font. Line width (separators/column alignment/raster
    sizing) scales with `bill.paper_width_mm` instead of assuming 58mm.
    """
    line_width = bill.line_width
    amount_w = 8
    label_w = line_width - amount_w
    sep = _text("-" * line_width)
    max_width_px = line_width * _PX_PER_CHAR

    out = _INIT
    logo_raster = (
        render_logo_to_escpos(bill.logo_image_bytes, max_width_px) if bill.logo_image_bytes else None
    )
    if logo_raster:
        out += _CENTER + logo_raster + b"\n" + _LEFT
    else:
        out += _CENTER + _BOLD_ON + _SIZE_DOUBLE + _text(bill.hotel_name) + _SIZE_NORMAL + _BOLD_OFF + _LEFT

    if bill.hotel_address_lines:
        out += _CENTER
        for addr_line in bill.hotel_address_lines:
            out += _text(addr_line)
        out += _LEFT
    if bill.gstin:
        out += _text(f"GSTIN: {bill.gstin}")
    out += sep
    # Table/waiter (what staff/kitchen call out) on the left; bill#/date-time (what a
    # customer cross-checks) on the right — requested directly during manual testing.
    date_str = bill.created_at.strftime("%d-%b-%Y %I:%M %p")
    for header_line in two_column_lines(bill.header_label, f"Bill #{bill.bill_number}", line_width):
        out += _text(header_line)
    waiter_label = f"Waiter: {bill.waiter_name}" if bill.waiter_name else ""
    for header_line in two_column_lines(waiter_label, date_str, line_width):
        out += _text(header_line)
    out += sep

    for line in bill.lines:
        item_desc = f"{line.quantity} x {line.name_en} @ {format_inr(line.unit_price, symbol='Rs.')}"
        out += _text(f"{item_desc:<{label_w}}{format_inr(line.line_total, symbol='Rs.'):>{amount_w}}")
        if bill.show_tamil_names and line.name_ta:
            out += _tamil_line(line.name_ta, max_width_px)

    out += sep
    out += _text(f"{'Subtotal':<{label_w}}{format_inr(bill.subtotal, symbol='Rs.'):>{amount_w}}")
    if bill.discount_note:
        for segment in bill.discount_note.split("; "):
            # Persisted with the on-screen ₹ glyph (bills.discount_note) — swap it for
            # print like every other amount here, then split so it right-aligns like
            # every other totals line.
            segment = segment.replace("₹", "Rs.")
            if ": " in segment:
                label, amount = segment.rsplit(": ", 1)
                out += _text(f"  {label:<{label_w - 2}}{amount:>{amount_w}}")
            else:
                out += _text(f"  {segment}")
    elif bill.discount_amount:
        discount_label = "-" + format_inr(bill.discount_amount, symbol="Rs.")
        out += _text(f"{'Discount':<{label_w}}{discount_label:>{amount_w}}")
    out += _text(f"{'CGST':<{label_w}}{format_inr(bill.cgst_amount, symbol='Rs.'):>{amount_w}}")
    out += _text(f"{'SGST':<{label_w}}{format_inr(bill.sgst_amount, symbol='Rs.'):>{amount_w}}")
    round_off_label = (
        f"+{format_inr(bill.round_off_amount, symbol='Rs.')}"
        if bill.round_off_amount >= 0
        else format_inr(bill.round_off_amount, symbol="Rs.")
    )
    out += _text(f"{'Round Off':<{label_w}}{round_off_label:>{amount_w}}")
    out += _BOLD_ON + _SIZE_DOUBLE_HEIGHT
    out += _text(f"{'Grand Total':<{label_w}}{format_inr(bill.grand_total, symbol='Rs.'):>{amount_w}}")
    out += _SIZE_NORMAL + _BOLD_OFF
    out += sep

    for method, amount in bill.payments:
        method_label = _PAYMENT_LABELS.get(method, method)
        out += _text(f"{method_label:<{label_w}}{format_inr(amount, symbol='Rs.'):>{amount_w}}")

    if bill.footer_message:
        out += sep
        out += _CENTER + _BOLD_ON + _text(bill.footer_message) + _BOLD_OFF + _LEFT

    if bill.qr_payload:
        out += _CENTER + generate_qr_escpos(bill.qr_payload) + b"\n" + _LEFT
    if bill.qr_payload and bill.upi_id:
        out += sep
        out += _text(f"Scan to pay via UPI ({bill.upi_id})")

    return out + b"\n\n" + _CUT
