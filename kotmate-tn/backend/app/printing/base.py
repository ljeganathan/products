from dataclasses import dataclass, field
from datetime import datetime


def format_inr(amount: float) -> str:
    """Indian lakh/crore digit grouping, ₹ prefix, paise shown only when non-zero —
    CLAUDE.md §9, mirrors the frontend's `formatINR` (frontend/src/lib/utils.ts) so
    printed amounts match what staff saw on screen.
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

    result = f"₹{grouped}"
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

    @property
    def header_label(self) -> str:
        return _compose_header_label(self.table_number, self.party_label, self.section_name_en)


def format_kot_text_lines(ticket: KotTicketRenderData) -> list[str]:
    """Shared plain-text layout both adapters build on — thermal wraps it in ESC/POS
    control bytes, dot-matrix emits it closer to verbatim (no image/formatting support).
    """
    lines = [
        f"KOT #{ticket.ticket_number}",
        ticket.header_label,
        ticket.created_at.strftime("%d-%b-%Y %I:%M %p"),
        "-" * 32,
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
    lines.append("-" * 32)
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

    @property
    def header_label(self) -> str:
        return _compose_header_label(self.table_number, self.party_label, self.section_name_en)


_PAYMENT_LABELS = {"upi": "UPI", "cash": "Cash", "card": "Card"}


def format_bill_text_lines(bill: BillRenderData) -> list[str]:
    """Shared plain-text layout for both bill adapters. `show_tamil_names` mirrors
    `hotel_master.show_tamil_names` — controls only the printed copy, never the POS
    staff-facing screen (CLAUDE.md §9).
    """
    lines = [bill.hotel_name, *bill.hotel_address_lines]
    if bill.gstin:
        lines.append(f"GSTIN: {bill.gstin}")
    lines.append("-" * 32)
    lines.append(f"Bill #{bill.bill_number}")
    lines.append(bill.header_label)
    lines.append(bill.created_at.strftime("%d-%b-%Y %I:%M %p"))
    lines.append("-" * 32)

    for line in bill.lines:
        name = (
            f"{line.name_en} / {line.name_ta}"
            if bill.show_tamil_names and line.name_ta
            else line.name_en
        )
        lines.append(f"{line.quantity} x {name} @ {format_inr(line.unit_price)}")
        lines.append(f"{'':>24}{format_inr(line.line_total):>8}")

    lines.append("-" * 32)
    lines.append(f"{'Subtotal':<24}{format_inr(bill.subtotal):>8}")
    if bill.discount_amount:
        lines.append(f"{'Discount':<24}{'-' + format_inr(bill.discount_amount):>8}")
    lines.append(f"{'CGST':<24}{format_inr(bill.cgst_amount):>8}")
    lines.append(f"{'SGST':<24}{format_inr(bill.sgst_amount):>8}")
    round_off_label = f"+{format_inr(bill.round_off_amount)}" if bill.round_off_amount >= 0 else format_inr(
        bill.round_off_amount
    )
    lines.append(f"{'Round Off':<24}{round_off_label:>8}")
    lines.append(f"{'Grand Total':<24}{format_inr(bill.grand_total):>8}")
    lines.append("-" * 32)

    for method, amount in bill.payments:
        lines.append(f"{_PAYMENT_LABELS.get(method, method):<24}{format_inr(amount):>8}")

    if bill.qr_payload and bill.upi_id:
        lines.append("-" * 32)
        lines.append(f"Scan to pay via UPI ({bill.upi_id})")

    return lines
