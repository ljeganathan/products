from app.printing.base import (
    BillRenderData,
    KotTicketRenderData,
    format_bill_text_lines,
    format_kot_text_lines,
)
from app.printing.qr import generate_qr_escpos

_ESC = b"\x1b"
_INIT = _ESC + b"@"
_BOLD_ON = _ESC + b"E\x01"
_BOLD_OFF = _ESC + b"E\x00"
_CUT = _ESC + b"i"
_CENTER = _ESC + b"a\x01"
_LEFT = _ESC + b"a\x00"


def render_kot(ticket: KotTicketRenderData) -> bytes:
    """ESC/POS byte stream for a thermal KOT printer (Pro/Pro Max, CLAUDE.md §10) —
    bold header, plain item lines, partial cut at the end.
    """
    text_lines = format_kot_text_lines(ticket)
    header, *rest = text_lines
    body = "\n".join(rest).encode("utf-8")
    return _INIT + _BOLD_ON + header.encode("utf-8") + b"\n" + _BOLD_OFF + body + b"\n\n\n" + _CUT


def render_bill(bill: BillRenderData) -> bytes:
    """ESC/POS byte stream for a thermal bill printer — bill printing is available on
    every plan tier (CLAUDE.md §6), unlike KOT physical printing which is Pro/Pro Max
    only. The UPI QR (when `bill.qr_payload` is set — gated by the `qr_upi` plan feature
    and a configured `hotel_master.upi_id`, resolved by the caller) is embedded as a
    centered raster image ahead of the trailing text, image support being the one thing
    that distinguishes the thermal adapter from dot-matrix here (CLAUDE.md §10).
    """
    text_lines = format_bill_text_lines(bill)
    header, *rest = text_lines
    body = "\n".join(rest).encode("utf-8")

    content = _INIT + _BOLD_ON + header.encode("utf-8") + b"\n" + _BOLD_OFF + body + b"\n"
    if bill.qr_payload:
        content += _CENTER + generate_qr_escpos(bill.qr_payload) + b"\n" + _LEFT
    return content + b"\n\n" + _CUT
