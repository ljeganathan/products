from app.printing.base import (
    BillRenderData,
    KotTicketRenderData,
    format_bill_text_lines,
    format_kot_text_lines,
)

_FORM_FEED = "\f"


def render_kot(ticket: KotTicketRenderData) -> str:
    """Plain ESC/P-compatible text for a dot-matrix KOT printer — no bold/image support,
    just the raw layout ending in a form feed so the next ticket starts on a fresh page.
    """
    return "\n".join(format_kot_text_lines(ticket)) + "\n" + _FORM_FEED


def render_bill(bill: BillRenderData) -> str:
    """Plain-text dot-matrix bill — no QR image (CLAUDE.md §10: dot-matrix has no image
    support at all), so the UPI id itself is printed as a text line instead when present,
    letting a customer key it in manually rather than scan it.
    """
    return "\n".join(format_bill_text_lines(bill)) + "\n" + _FORM_FEED
