from datetime import date, datetime

from pydantic import BaseModel


class SalesReportDayOut(BaseModel):
    bucket: datetime
    total_paise: int
    bill_count: int


class SalesReportOut(BaseModel):
    date_from: date
    date_to: date
    range_clamped: bool
    total_paise: int
    bill_count: int
    avg_bill_paise: int
    profit_paise: int
    daily: list[SalesReportDayOut]


class GstSummaryOut(BaseModel):
    date_from: date
    date_to: date
    range_clamped: bool
    subtotal_paise: int
    discount_paise: int
    cgst_paise: int
    sgst_paise: int
    total_paise: int
    bill_count: int
