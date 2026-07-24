import uuid
from datetime import datetime

from pydantic import BaseModel


class TopItemOut(BaseModel):
    name: str
    revenue_paise: int


class DashboardSummaryOut(BaseModel):
    total_paise: int
    bill_count: int
    avg_bill_paise: int
    top_items: list[TopItemOut]
    low_stock_count: int


class TrendPointOut(BaseModel):
    bucket: datetime
    total_paise: int
    bill_count: int


class BreakdownRowOut(BaseModel):
    label: str
    total_paise: int
    bill_count: int


class StoreTotalOut(BaseModel):
    store_id: uuid.UUID
    store_name: str
    total_paise: int
    bill_count: int
