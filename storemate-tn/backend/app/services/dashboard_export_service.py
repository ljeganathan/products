"""Pro Max dashboard PDF export (`GET /dashboard/export.pdf`).

Deviation from the phase brief's suggested `weasyprint`: weasyprint needs
Cairo/Pango/GDK-Pixbuf system libraries that would bloat the `python:3.11-
slim` image and its `apt-get install` list (backend/Dockerfile) just to
render a handful of KPI tables. `reportlab` is pure-Python-installable (no
system packages beyond what's already in the image) and draws PDF content
directly — "similar lightweight" per the brief, just not HTML-driven. If a
templated, designer-editable PDF layout is ever needed, swap this module's
internals for weasyprint then; callers only ever see `render_dashboard_pdf`
returning bytes.
"""

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.repositories.dashboard_repository import DashboardSummary, StoreTotal
from app.utils.currency import format_paise_inr

_TABLE_STYLE = TableStyle(
    [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]
)


def render_dashboard_pdf(
    *,
    tenant_name: str,
    summary: DashboardSummary,
    store_totals: list[StoreTotal],
    date_from: date,
    date_to: date,
    generated_at: str,
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title=f"{tenant_name} — StoreMate TN Dashboard"
    )
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(f"{tenant_name} — Dashboard Export", styles["Title"]),
        Paragraph(
            f"Period: {date_from.isoformat()} to {date_to.isoformat()} · Generated {generated_at}",
            styles["Normal"],
        ),
        Spacer(1, 12 * mm / 10),
        Paragraph("Today's snapshot", styles["Heading2"]),
        Table(
            [
                ["Metric", "Value"],
                ["Sales today", format_paise_inr(summary["total_paise"])],
                ["Bills today", str(summary["bill_count"])],
                ["Average bill value", format_paise_inr(summary["avg_bill_paise"])],
            ],
            colWidths=[220, 200],
            style=_TABLE_STYLE,
        ),
        Spacer(1, 8 * mm / 10),
    ]

    if summary["top_items"]:
        elements.append(Paragraph("Top items today", styles["Heading2"]))
        elements.append(
            Table(
                [["Item", "Revenue"]]
                + [[i["name"], format_paise_inr(i["revenue_paise"])] for i in summary["top_items"]],
                colWidths=[280, 140],
                style=_TABLE_STYLE,
            )
        )
        elements.append(Spacer(1, 8 * mm / 10))

    if store_totals:
        period_label = f"Store totals ({date_from.isoformat()} to {date_to.isoformat()})"
        elements.append(Paragraph(period_label, styles["Heading2"]))
        elements.append(
            Table(
                [["Store", "Sales", "Bills"]]
                + [
                    [s["store_name"], format_paise_inr(s["total_paise"]), str(s["bill_count"])]
                    for s in store_totals
                ],
                colWidths=[220, 140, 60],
                style=_TABLE_STYLE,
            )
        )

    doc.build(elements)
    return buffer.getvalue()
