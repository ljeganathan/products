from app.printing.base import format_inr, line_chars_for_paper_width

# Generic column-table plain-text formatter, independent of export_service.py's
# PDF/Excel/CSV path (thermal/dot-matrix printers can't render a PDF — they need plain
# ESC/POS-safe text, same as the KOT ticket and bill templates already produce). Reuses
# export_service.rows_as_grid for the header/row extraction so a report's printed and
# exported column labels never drift apart.

# Floor so a currency/amount column can't collapse to something unreadable (e.g. a
# 4-char slot truncating "1,25,000.00") once a report has 4+ columns on a narrow 58mm
# (32-char) printer — verified against Item Wise Sales (name_en, name_ta, quantity_sold,
# revenue, 4 columns after report_print_service.py's exclude_id_fields drops item_id) at
# all three paper-width presets (58/80/241mm) plus a custom mm value.
_MIN_COLUMN_WIDTH = 6


def _cell_text(cell: object) -> str:
    # Every float field across the report row models (revenue, net_sale_value,
    # incentive_amount, subtotal, grand_total, ...) represents a rupee amount — format
    # it the same way bill/KOT printing already does (CLAUDE.md §9 Indian digit
    # grouping) rather than printing a raw Python float like "125000.5". Kept local to
    # the print path — export_service's own _coerce_cell deliberately leaves floats
    # untouched for CSV/Excel/PDF, which want a real numeric type, not a formatted string.
    if isinstance(cell, float):
        return format_inr(cell, symbol="Rs.")
    return str(cell)


def _column_widths(headers: list[str], rows: list[list[object]], width: int) -> list[int]:
    n = len(headers)
    if n == 0:
        return []
    if n == 1:
        return [width]

    # Content-aware: size each column to what it actually needs (header or widest cell),
    # not a blind 40%-first/equal-split-rest rule that starved numeric columns.
    natural = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            cell_len = len(_cell_text(cell))
            if cell_len > natural[i]:
                natural[i] = cell_len
    total_natural = sum(natural)

    if total_natural <= width:
        # Room to spare — hand it to the first (label) column for readability, same
        # convention a real till-roll Z-report/summary uses (wide label, tight numbers).
        widths = list(natural)
        widths[0] += width - total_natural
        return widths

    # Doesn't fit. The last column is almost always the primary money figure (revenue,
    # net_sale_value, incentive_amount, grand_total, ...) — a truncated name is still
    # identifiable at a glance, but a truncated amount ("Rs.1,25," missing its own
    # total) is actively misleading on a document meant to be trusted. So on a genuinely
    # tight printer, protect the last column up to its natural width first, and only
    # shrink the earlier (mostly text) columns down to the floor.
    last_w = min(natural[-1], max(_MIN_COLUMN_WIDTH, width - _MIN_COLUMN_WIDTH * (n - 1)))
    remaining = width - last_w
    lead_natural = natural[:-1]
    lead_total = sum(lead_natural) or 1
    lead_widths = [max(_MIN_COLUMN_WIDTH, round(w * remaining / lead_total)) for w in lead_natural]
    overflow = sum(lead_widths) - remaining
    guard = 0
    while overflow > 0 and guard < remaining * (n - 1):
        i = max(range(n - 1), key=lambda i: lead_widths[i])
        if lead_widths[i] > _MIN_COLUMN_WIDTH:
            lead_widths[i] -= 1
            overflow -= 1
        guard += 1
        if all(w <= _MIN_COLUMN_WIDTH for w in lead_widths):
            break  # every lead column is already at the floor — let rows truncate instead
    return [*lead_widths, last_w]


def _format_row(cells: list[object], widths: list[int]) -> str:
    parts: list[str] = []
    for i, cell in enumerate(cells):
        w = widths[i]
        text = _cell_text(cell)[:w]
        parts.append(text.ljust(w) if i == 0 else text.rjust(w))
    return "".join(parts)


def render_report_text(
    title: str,
    headers: list[str],
    rows: list[list[object]],
    paper_width_mm: int | None,
    generated_at_label: str | None = None,
) -> bytes:
    """`rows` (including any totals row) is already the plain grid produced by
    `export_service.rows_as_grid` — this only handles the plain-text layout, not the
    report's own data computation.
    """
    width = line_chars_for_paper_width(paper_width_mm)
    sep = "-" * width
    widths = _column_widths(headers, rows, width)

    lines = [title[:width].center(width)]
    if generated_at_label:
        lines.append(generated_at_label[:width].center(width))
    lines.append(sep)
    lines.append(_format_row(headers, widths))
    lines.append(sep)
    for row in rows:
        lines.append(_format_row(row, widths))
    lines.append(sep)

    return ("\n".join(lines) + "\n").encode("utf-8")
