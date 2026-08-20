import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

EXPORT_FORMATS = ("csv", "excel", "pdf")

_MEDIA_TYPES = {
    "csv": "text/csv",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}
_EXTENSIONS = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}


def _to_csv(headers: list[str], grid: list[list[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(grid)
    # utf-8-sig so Excel opens Tamil (and other non-ASCII) names correctly rather than
    # mangling them via a default codepage guess.
    return buffer.getvalue().encode("utf-8-sig")


def _to_excel(title: str, headers: list[str], grid: list[list[object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title[:31] or "Report"  # Excel sheet-name length limit

    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in grid:
        ws.append(row)

    for column_cells in ws.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=10)
        ws.column_dimensions[column_cells[0].column_letter].width = min(max(length + 2, 10), 40)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _to_pdf(title: str, headers: list[str], grid: list[list[object]]) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4) if len(headers) > 5 else A4,
        title=title,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(title, styles["Title"]), Spacer(1, 12)]

    table_data = [headers] + [[str(v) for v in row] for row in grid]
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6f4e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f2f2")]),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()


def export_grid(title: str, headers: list[str], grid: list[list[object]], fmt: str) -> tuple[bytes, str, str]:
    """Renders a pre-built header/row grid into csv/excel/pdf bytes — shared by all
    report export endpoints. Headers and rows are supplied by the caller (report_print_
    service.build_report_body + report_body_to_grid) rather than reflected from a
    Pydantic model's raw field names, so every export format shows the exact same
    renamed/no-id column set the printer version already uses (production feedback
    round 4: "keep the same format of the columns... for csv/pdf/excel").
    """
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")

    filename_stem = title.lower().replace(" ", "_")

    if fmt == "csv":
        content = _to_csv(headers, grid)
    elif fmt == "excel":
        content = _to_excel(title, headers, grid)
    else:
        content = _to_pdf(title, headers, grid)

    return content, _MEDIA_TYPES[fmt], f"{filename_stem}.{_EXTENSIONS[fmt]}"
