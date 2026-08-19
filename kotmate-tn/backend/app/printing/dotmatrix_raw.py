from app.printing import report_print
from app.printing.base import (
    BillRenderData,
    KotTicketRenderData,
    ReportRenderData,
    format_bill_text_lines,
    format_kot_text_lines,
    line_chars_for_paper_width,
    now_ist,
    two_column_lines,
)

_FORM_FEED = "\f"


def render_test_print(paper_width_mm: int | None) -> str:
    """Plain-text counterpart to `escpos_thermal.render_test_print` — no bold/size
    control codes, just the same content for the Printers settings "Test Print" button.
    """
    line_width = line_chars_for_paper_width(paper_width_mm)
    sep = "-" * line_width
    lines = [
        "KOTMate TN",
        "Test Print",
        sep,
        "If you can read this, the",
        "printer is set up correctly.",
        sep,
        now_ist().strftime("%d-%b-%Y %I:%M %p"),
    ]
    return "\n".join(lines) + "\n" + _FORM_FEED


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


def render_report(data: ReportRenderData) -> str:
    """Plain-text dot-matrix counterpart to escpos_thermal.render_report — same branch
    header/timestamp/body structure, but no bold or double-height (dot-matrix can't) and
    `body.tamil_names` is ignored entirely: dot-matrix has no image support at all
    (CLAUDE.md §10), so a Tamil name can never be rasterized here — every row always
    prints its plain-text name (English), the same accepted limitation
    format_bill_text_lines/format_kot_text_lines already have for dot-matrix Tamil.
    """
    line_width = line_chars_for_paper_width(data.paper_width_mm)
    sep = "-" * line_width

    lines: list[str] = []
    for text in [data.branch_name, *data.branch_address_lines]:
        lines.extend(report_print.wrap_line(text, line_width))
    if data.branch_gstin:
        lines.extend(report_print.wrap_line(f"GSTIN: {data.branch_gstin}", line_width))
    lines.append(sep)
    lines.extend(report_print.wrap_line(data.title, line_width))
    lines.extend(report_print.wrap_line(data.printed_at_label, line_width))
    for text in data.extra_header_lines:
        lines.extend(report_print.wrap_line(text, line_width))
    lines.append(sep)

    body = data.body
    if body.kind == "keyvalue":
        for label, value in body.pairs:
            lines.extend(two_column_lines(label, value, line_width))
    else:
        widths = report_print.column_widths(body.headers, body.rows, line_width)
        lines.append(report_print.format_row(body.headers, widths))
        lines.append(sep)
        for row in body.rows:
            lines.append(report_print.format_row(row, widths))

    lines.append(sep)
    return "\n".join(lines) + "\n" + _FORM_FEED
