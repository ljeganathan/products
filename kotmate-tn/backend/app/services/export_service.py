import csv
import io

from openpyxl import Workbook
from openpyxl.styles import Font
from pydantic import BaseModel
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


def _humanize(field_name: str) -> str:
    return field_name.replace("_", " ").title()


def _coerce_cell(value: object) -> object:
    # openpyxl only accepts a narrow set of native types per cell — a raw UUID (every
    # report row's id field) raises ValueError otherwise. int/float/bool/None pass
    # through untouched so Excel still treats them as real numbers, not text.
    if value is None or isinstance(value, int | float | bool):
        return value
    return str(value)


def rows_as_grid(
    row_model: type[BaseModel],
    rows: list[BaseModel],
    totals_row: dict[str, object] | None,
    *,
    exclude_id_fields: bool = False,
) -> tuple[list[str], list[list[object]]]:
    """`exclude_id_fields` drops every `*_id` field (e.g. `pos_user_id`) before
    building headers/grid — a raw UUID is legitimately useful in an exported CSV/Excel/
    PDF for back-office reconciliation (the default), but on a printed thermal receipt
    it's just noise that steals width a report already spends on the human-readable
    `login_id`/`name` columns on the same row (report_print_service.py).
    """
    field_names = [f for f in row_model.model_fields if not (exclude_id_fields and f.endswith("_id"))]
    headers = [_humanize(f) for f in field_names]
    grid = [[_coerce_cell(getattr(r, f)) for f in field_names] for r in rows]
    if totals_row is not None:
        grid.append([_coerce_cell(totals_row.get(f, "")) for f in field_names])
    return headers, grid


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


def export_rows(
    title: str,
    row_model: type[BaseModel],
    rows: list[BaseModel],
    fmt: str,
    totals_row: dict[str, object] | None = None,
) -> tuple[bytes, str, str]:
    """Renders any list of Pydantic row models into csv/excel/pdf bytes — shared by all
    8 report endpoints rather than a bespoke exporter per report type. `row_model` is
    taken explicitly (not inferred from `rows[0]`) so an empty report still exports a
    file with the correct headers.
    """
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {fmt}")

    headers, grid = rows_as_grid(row_model, rows, totals_row)
    filename_stem = title.lower().replace(" ", "_")

    if fmt == "csv":
        content = _to_csv(headers, grid)
    elif fmt == "excel":
        content = _to_excel(title, headers, grid)
    else:
        content = _to_pdf(title, headers, grid)

    return content, _MEDIA_TYPES[fmt], f"{filename_stem}.{_EXTENSIONS[fmt]}"
