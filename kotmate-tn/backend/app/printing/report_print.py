from app.printing.base import line_chars_for_paper_width

# Low-level, printer-agnostic layout helpers shared by escpos_thermal.render_report and
# dotmatrix_raw.render_report — the actual byte/text rendering (branch header, bold/big
# rows, Tamil rasterization) lives in those two adapters since they diverge by printer
# type; this module only knows how to size and lay out a grid's columns on a fixed
# character width, and how to lay out the report's separator/rule lines.

# Floor so a currency/amount column can't collapse to something unreadable (e.g. a
# 4-char slot truncating "1,25,000.00") once a report has several columns on a narrow
# 58mm (32-char) printer — verified against a wide report at all three paper-width
# presets (58/80/241mm) plus a custom mm value.
_MIN_COLUMN_WIDTH = 6


def column_widths(
    headers: list[str],
    rows: list[list[str]],
    width: int,
    expand_column: int = 0,
    max_widths: dict[int, int] | None = None,
) -> list[int]:
    """Returns each column's own character width — `format_row` below joins them with a
    single delimiter space, so the total printed width is `sum(widths) + (n - 1)`, not
    `width` itself; every width computed here already accounts for that.

    `expand_column` picks which column absorbs leftover width when everything already
    fits (defaults to 0 — the label column, for every existing report). Item List's
    print body is the one exception: its column 0 is "Code", not the label, so it
    passes `expand_column=1` to hand any surplus to "Name" instead. `max_widths` caps
    a column's natural width regardless of its own content (Item List again — item
    codes are 4-digit by convention, so an outlier longer code shouldn't blow up the
    Code column or steal width the Name column actually needs).
    """
    n = len(headers)
    if n == 0:
        return []
    if n == 1:
        return [width]

    # One literal space between each pair of adjacent columns (reserved here, inserted
    # by format_row) — without it, two right-aligned columns that each exactly fill
    # their own natural width run together with no visible gap (e.g. "Qty"+"Sales" ->
    # "QtySales"), which a bare rjust()/ljust() pair can silently produce whenever a
    # narrow report leaves no incidental slack in either column.
    usable = width - (n - 1)

    # Content-aware: size each column to what it actually needs (header or widest cell),
    # not a blind 40%-first/equal-split-rest rule that starved numeric columns.
    natural = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if len(cell) > natural[i]:
                natural[i] = len(cell)
    for i, cap in (max_widths or {}).items():
        natural[i] = min(natural[i], cap)
    total_natural = sum(natural)

    if total_natural <= usable:
        # Room to spare — hand it to the expand column (the label, for every report
        # except Item List) for readability, same convention a real till-roll
        # Z-report/summary uses (wide label, tight numbers).
        widths = list(natural)
        widths[expand_column] += usable - total_natural
        return widths

    # Doesn't fit. The last column is almost always the primary money figure (revenue,
    # net_sale_value, incentive_amount, grand_total, ...) — a truncated name is still
    # identifiable at a glance, but a truncated amount ("1,25," missing its own total)
    # is actively misleading on a document meant to be trusted. So on a genuinely tight
    # printer, protect the last column up to its natural width first, and only shrink
    # the earlier (mostly text) columns down to the floor.
    last_w = min(natural[-1], max(_MIN_COLUMN_WIDTH, usable - _MIN_COLUMN_WIDTH * (n - 1)))
    remaining = usable - last_w
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


def format_row(cells: list[str], widths: list[int], left_align_columns: set[int] | None = None) -> str:
    """`left_align_columns` defaults to `{0}` — every grid report has exactly one
    leading text column followed by right-aligned numeric ones, except Item List's
    print body (Code, Name both text), which passes `{0, 1}` explicitly instead of
    letting its Name column fall under the numeric-column default.
    """
    if left_align_columns is None:
        left_align_columns = {0}
    parts: list[str] = []
    for i, cell in enumerate(cells):
        w = widths[i]
        text = cell[:w]
        parts.append(text.ljust(w) if i in left_align_columns else text.rjust(w))
    return " ".join(parts)


def separator_line(paper_width_mm: int | None) -> str:
    return "-" * line_chars_for_paper_width(paper_width_mm)


def wrap_line(text: str, width: int) -> list[str]:
    """Greedy word-wrap for header lines (branch name/address, title, timestamp, Z-Report's
    "Shift Close Time"/"Closed By" lines) — those are plain sentences, not column data, so
    they need wrapping rather than the grid's truncate-to-column-width behavior. Without
    this, a line longer than the printer's line width (e.g. "Shift Close Time: 19-Aug-2026
    03:45 PM" easily exceeds a 58mm/32-column printer) would either get cut off or, on real
    hardware, wrap at an arbitrary column mid-word.
    """
    if width <= 0 or len(text) <= width:
        return [text]
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while len(word) > width:
            lines.append(word[:width])
            word = word[width:]
        current = word
    if current:
        lines.append(current)
    return lines or [text[:width]]
