import uuid
from datetime import date

from pydantic import BaseModel


class TopItemRow(BaseModel):
    item_id: uuid.UUID
    name_en: str
    quantity_sold: int


class HourlySalesPoint(BaseModel):
    hour: int
    sales: float


class DashboardSummaryResponse(BaseModel):
    """Basic KPIs available at every plan tier (CLAUDE.md §6 — Lite gets "basic KPIs").
    `hourly_trend` is always returned (cheap to compute alongside everything else); the
    frontend decides whether to render it as a chart based on the tenant's plan.
    """

    report_date: date
    today_sales: float
    bill_count: int
    average_bill_value: float
    top_items: list[TopItemRow]
    hourly_trend: list[HourlySalesPoint]


class LowStockItemRow(BaseModel):
    item_id: uuid.UUID
    name_en: str
    name_ta: str | None
    available_qty: int


class LowStockItemsResponse(BaseModel):
    rows: list[LowStockItemRow]


class LocationComparisonRow(BaseModel):
    location_id: uuid.UUID
    location_name: str
    sales: float
    bill_count: int


class MultiLocationComparisonResponse(BaseModel):
    rows: list[LocationComparisonRow]
