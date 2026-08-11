import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Tenant
from app.printing.base import format_inr
from app.schemas.platform import InvoiceResponse

# Reportlab's base14 fonts (Helvetica) have no ₹ (U+20B9) glyph — same reason the
# thermal/dot-matrix print adapters swap it for "Rs." (printing/base.py's format_inr
# docstring); a PDF viewer renders the missing glyph as a blank box otherwise.
_CURRENCY_SYMBOL = "Rs."


def render_invoice_pdf(invoice: InvoiceResponse, tenant: Tenant) -> bytes:
    """One-page formal invoice for the Product Owner console's "Download PDF" action
    (CLAUDE.md §8 `invoices` — tenant subscription billing, distinct from POS `bills`).
    Invoices have no separate email-delivery mechanism in this codebase; `status="sent"`
    on creation is only ever a status label, not a dispatched email.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Invoice {invoice.invoice_number}",
        topMargin=24 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("KOTMate TN", styles["Title"]),
        Paragraph("Subscription Invoice", styles["Heading3"]),
        Spacer(1, 16),
    ]

    address_fields = [
        tenant.door_no, tenant.street, tenant.city, tenant.district, tenant.state, tenant.pincode,
    ]
    address_parts = [p for p in address_fields if p]
    elements.append(Paragraph(f"<b>Bill To:</b> {tenant.company_name}", styles["Normal"]))
    if address_parts:
        elements.append(Paragraph(", ".join(address_parts), styles["Normal"]))
    if tenant.email:
        elements.append(Paragraph(tenant.email, styles["Normal"]))
    elements.append(Spacer(1, 16))

    meta = Table(
        [
            ["Invoice #", invoice.invoice_number],
            ["Issued Date", str(invoice.issued_date)],
            ["Due Date", str(invoice.due_date)],
            ["Status", invoice.status.upper()],
            *([["Paid Date", str(invoice.paid_date)]] if invoice.paid_date else []),
        ],
        colWidths=[100, 200],
    )
    meta.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    elements.append(meta)
    elements.append(Spacer(1, 16))

    amount_label = format_inr(invoice.amount, symbol=_CURRENCY_SYMBOL)
    items = Table(
        [
            ["Description", "Amount"],
            [invoice.description or "Subscription charge", amount_label],
        ],
        colWidths=[350, 100],
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6f4e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(items)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>Total: {amount_label}</b>", styles["Heading3"]))

    doc.build(elements)
    return buffer.getvalue()
