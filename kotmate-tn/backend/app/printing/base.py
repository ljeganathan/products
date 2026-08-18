from dataclasses import dataclass, field
from datetime import datetime

# 58mm -> 32 columns is the convention every line-formatting call below was originally
# built against; 80mm printers physically fit more (~48 cols at the same font), and
# hardcoding 32 regardless of `paper_width_mm` (Printers settings, CLAUDE.md §10) is
# why 80mm receipts printed with a lot of unused space on the right. 241mm is dot-matrix
# continuous stationery (much wider); anything else falls back to the same 58mm ratio.
_PAPER_WIDTH_PRESETS_MM = {58: 32, 80: 48, 241: 128}
_DEFAULT_LINE_WIDTH = 32


def line_chars_for_paper_width(paper_width_mm: int | None) -> int:
    if paper_width_mm is None:
        return _DEFAULT_LINE_WIDTH
    if paper_width_mm in _PAPER_WIDTH_PRESETS_MM:
        return _PAPER_WIDTH_PRESETS_MM[paper_width_mm]
    return max(24, round(paper_width_mm * _DEFAULT_LINE_WIDTH / 58))


def format_inr(amount: float, symbol: str = "₹") -> str:
    """Indian lakh/crore digit grouping, ₹ prefix, paise shown only when non-zero —
    CLAUDE.md §9, mirrors the frontend's `formatINR` (frontend/src/lib/utils.ts) so
    printed amounts match what staff saw on screen.

    `symbol` defaults to the real ₹ glyph for every other caller (e.g. discount_note,
    which also feeds the on-screen bill preview via `bills.discount_note`) but the
    print-byte renderers below pass "Rs." instead — ₹ (U+20B9) isn't in any thermal
    printer's built-in code-page font, so sending it as-is prints as garbage/blank on
    real hardware even though it renders fine on screen.
    """
    negative = amount < 0
    paise_total = round(abs(amount) * 100)
    rupees, paise = divmod(paise_total, 100)

    digits = str(rupees)
    if len(digits) > 3:
        last3, rest = digits[-3:], digits[:-3]
        groups: list[str] = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        grouped = ",".join([*groups, last3])
    else:
        grouped = digits

    result = f"{symbol}{grouped}"
    if paise:
        result += f".{paise:02d}"
    return f"-{result}" if negative else result


@dataclass
class KotTicketLine:
    name_en: str
    name_ta: str | None
    quantity: int
    notes: str | None = None


def _compose_header_label(table_number: str | None, party_label: str | None, section_name_en: str) -> str:
    """Table number stays the single dominant element (CLAUDE.md §9); the customer
    label (Phase 21, e.g. "Customer-2") is secondary, section name is tertiary — e.g.
    "T5 Customer-2 (AC)". Falls back to the pre-Phase-21 format when there's no
    party_label (non-seating sections, or any order predating this feature).
    """
    if not table_number:
        return section_name_en
    if party_label:
        return f"{table_number} {party_label} ({section_name_en})"
    return f"{table_number} ({section_name_en})"


@dataclass
class KotTicketRenderData:
    """Everything an adapter needs to render one KOT ticket — table number + section
    together in the header (CLAUDE.md §10) so kitchen staff know the order type at a
    glance, whether that's a physical table or a Takeaway/Online Delivery ticket.
    """

    ticket_number: str
    table_number: str | None
    section_name_en: str
    created_at: datetime
    lines: list[KotTicketLine] = field(default_factory=list)
    # `hotel_master.show_tamil_names` (Phase 10) — controls the printed KOT only, never
    # the POS/KDS staff-facing screen, which always shows both languages (CLAUDE.md §9).
    # Defaults True so a location with no Hotel Master saved yet behaves as before.
    show_tamil_names: bool = True
    # Which customer/party slot at the table this ticket belongs to (Phase 21).
    party_label: str | None = None
    # Sourced from the KOT printer's own `paper_width_mm` (Printers settings) — None
    # (no printer width configured yet) falls back to the original 58mm/32-col layout.
    paper_width_mm: int | None = None

    @property
    def header_label(self) -> str:
        return _compose_header_label(self.table_number, self.party_label, self.section_name_en)

    @property
    def line_width(self) -> int:
        return line_chars_for_paper_width(self.paper_width_mm)


def format_kot_text_lines(ticket: KotTicketRenderData) -> list[str]:
    """Shared plain-text layout both adapters build on — thermal wraps it in ESC/POS
    control bytes, dot-matrix emits it closer to verbatim (no image/formatting support).
    """
    sep = "-" * ticket.line_width
    lines = [
        f"KOT #{ticket.ticket_number}",
        ticket.header_label,
        ticket.created_at.strftime("%d-%b-%Y %I:%M %p"),
        sep,
    ]
    for line in ticket.lines:
        name = (
            f"{line.name_en} / {line.name_ta}"
            if ticket.show_tamil_names and line.name_ta
            else line.name_en
        )
        lines.append(f"{line.quantity} x {name}")
        if line.notes:
            lines.append(f"    ({line.notes})")
    lines.append(sep)
    return lines


@dataclass
class BillLine:
    name_en: str
    name_ta: str | None
    quantity: int
    unit_price: float
    line_total: float


@dataclass
class BillRenderData:
    """Everything an adapter needs to render one finalized bill (Phase 09). CGST/SGST
    are always rendered as two distinct amounts (CLAUDE.md §9) and Round Off always
    prints as its own line, even when it's ₹0.00 — never silently absorbed.

    `qr_payload` is the `upi://pay?...` deep link to embed as a QR image, already
    resolved by the caller (None when the tenant's plan doesn't include `qr_upi`, or the
    location has no UPI id configured) so the printing layer never needs plan/feature
    knowledge of its own.
    """

    bill_number: str
    table_number: str | None
    section_name_en: str
    created_at: datetime
    lines: list[BillLine]
    subtotal: float
    discount_amount: float
    # Breakdown of which discount rule(s) applied, e.g. "Festival Offer: -₹45.00;
    # Coupon WELCOME10: -₹15.00" — one printed line per "; "-separated segment, so the
    # customer sees which named offer(s) reduced the bill (CLAUDE.md Phase 23).
    discount_note: str | None
    cgst_amount: float
    sgst_amount: float
    round_off_amount: float
    grand_total: float
    payments: list[tuple[str, float]]
    hotel_name: str
    hotel_address_lines: list[str]
    gstin: str | None
    upi_id: str | None
    qr_payload: str | None
    show_tamil_names: bool
    # Which customer/party slot at the table this bill belongs to (Phase 21) —
    # snapshotted onto `bills.party_label` at finalize time, same as table/section/waiter.
    party_label: str | None = None
    # Assigned waiter's name, if any (CLAUDE.md §11) — printed only when the bill
    # actually has one; a walk-in cashier-only sale has no waiter line at all.
    waiter_name: str | None = None
    # Sourced from the bill printer's own `paper_width_mm` (Printers settings) — None
    # falls back to the original 58mm/32-col layout.
    paper_width_mm: int | None = None
    # Raw bytes of `hotel_master.logo_url`'s file, already read from disk by the caller
    # (None when no logo uploaded, or the file couldn't be read) — the thermal adapter
    # embeds it as a raster image; when absent it prints the hotel name large/bold/
    # centered instead. Dot-matrix has no image support (CLAUDE.md §10) either way.
    logo_image_bytes: bytes | None = None
    # Printed centered near the end of the receipt (e.g. "Thank You & Visit Again..!!!")
    # — `hotel_master.receipt_footer_message`, tenant-editable in Settings; None means
    # the hotel hasn't set one and nothing extra prints (no hardcoded default here, the
    # service layer resolves a fallback so printing stays a pure function of this field).
    footer_message: str | None = None

    @property
    def header_label(self) -> str:
        return _compose_header_label(self.table_number, self.party_label, self.section_name_en)

    @property
    def line_width(self) -> int:
        return line_chars_for_paper_width(self.paper_width_mm)


_PAYMENT_LABELS = {"upi": "UPI", "cash": "Cash", "card": "Card"}


def two_column_lines(left: str, right: str, line_width: int) -> list[str]:
    """Left-aligned text pinned to the left edge, right-aligned text pinned to the
    right edge, on the same line when they both fit — used for the bill header's
    Table/Waiter (left) vs Bill#/Date-time (right) pairing. A long table/customer/
    section label (e.g. "T1 Customer-2 (Non-AC)") plus a fixed guess at the right
    column's width was overflowing a 32-col/58mm line and colliding with no separating
    space — this sizes the right column to the actual right-text length and falls back
    to two separate lines (instead of a garbled single line) whenever the pair genuinely
    doesn't fit the printer's width.
    """
    if not left:
        return [f"{right:>{line_width}}"] if right else []
    if not right:
        return [left]
    if len(left) + 1 + len(right) <= line_width:
        return [f"{left}{right:>{line_width - len(left)}}"]
    return [left, f"{right:>{line_width}}"]


def format_bill_text_lines(bill: BillRenderData) -> list[str]:
    """Shared plain-text layout for both bill adapters. `show_tamil_names` mirrors
    `hotel_master.show_tamil_names` — controls only the printed copy, never the POS
    staff-facing screen (CLAUDE.md §9).

    Amounts print with "Rs." instead of the ₹ glyph — thermal/dot-matrix printer
    firmware fonts don't include ₹ (U+20B9), so the real symbol prints as garbage or
    blank on physical hardware even though it renders correctly on screen (CLAUDE.md
    §9's ₹ formatting is a screen-display rule; this is the physical-print adapter).
    """
    sep = "-" * bill.line_width
    amount_w = 8
    label_w = bill.line_width - amount_w

    lines = [bill.hotel_name, *bill.hotel_address_lines]
    if bill.gstin:
        lines.append(f"GSTIN: {bill.gstin}")
    lines.append(sep)
    # Table/waiter (what staff/kitchen call out) on the left; bill#/date-time (what a
    # customer cross-checks) on the right — two lines, not four, per-side grouping
    # requested directly during manual testing.
    date_str = bill.created_at.strftime("%d-%b-%Y %I:%M %p")
    lines.extend(two_column_lines(bill.header_label, f"Bill #{bill.bill_number}", bill.line_width))
    waiter_label = f"Waiter: {bill.waiter_name}" if bill.waiter_name else ""
    lines.extend(two_column_lines(waiter_label, date_str, bill.line_width))
    lines.append(sep)

    for line in bill.lines:
        name = (
            f"{line.name_en} / {line.name_ta}"
            if bill.show_tamil_names and line.name_ta
            else line.name_en
        )
        item_desc = f"{line.quantity} x {name} @ {format_inr(line.unit_price, symbol='Rs.')}"
        lines.append(f"{item_desc:<{label_w}}{format_inr(line.line_total, symbol='Rs.'):>{amount_w}}")

    lines.append(sep)
    lines.append(f"{'Subtotal':<{label_w}}{format_inr(bill.subtotal, symbol='Rs.'):>{amount_w}}")
    if bill.discount_note:
        for segment in bill.discount_note.split("; "):
            # Segments are "<rule name>: -₹X.XX" as persisted for on-screen display
            # (bills.discount_note) — swap the glyph for print the same as everywhere
            # else, then split so the amount right-aligns in the same column as every
            # other totals line instead of trailing inline after a variable-length name.
            segment = segment.replace("₹", "Rs.")
            if ": " in segment:
                label, amount = segment.rsplit(": ", 1)
                lines.append(f"  {label:<{label_w - 2}}{amount:>{amount_w}}")
            else:
                lines.append(f"  {segment}")
    elif bill.discount_amount:
        discount_label = "-" + format_inr(bill.discount_amount, symbol="Rs.")
        lines.append(f"{'Discount':<{label_w}}{discount_label:>{amount_w}}")
    # Zero-rated tax lines are skipped to save space on narrow paper (production
    # feedback) — CGST/SGST still always print as two separate lines whenever either is
    # actually nonzero, never merged into one (CLAUDE.md §9).
    if bill.cgst_amount:
        lines.append(f"{'CGST':<{label_w}}{format_inr(bill.cgst_amount, symbol='Rs.'):>{amount_w}}")
    if bill.sgst_amount:
        lines.append(f"{'SGST':<{label_w}}{format_inr(bill.sgst_amount, symbol='Rs.'):>{amount_w}}")
    round_off_label = (
        f"+{format_inr(bill.round_off_amount, symbol='Rs.')}"
        if bill.round_off_amount >= 0
        else format_inr(bill.round_off_amount, symbol="Rs.")
    )
    lines.append(f"{'Round Off':<{label_w}}{round_off_label:>{amount_w}}")
    lines.append(f"{'Grand Total':<{label_w}}{format_inr(bill.grand_total, symbol='Rs.'):>{amount_w}}")
    lines.append(sep)

    for method, amount in bill.payments:
        method_label = _PAYMENT_LABELS.get(method, method)
        lines.append(f"{method_label:<{label_w}}{format_inr(amount, symbol='Rs.'):>{amount_w}}")

    if bill.footer_message:
        lines.append(sep)
        lines.append(bill.footer_message)

    if bill.qr_payload and bill.upi_id:
        lines.append(sep)
        lines.append(f"Scan to pay via UPI ({bill.upi_id})")

    return lines
