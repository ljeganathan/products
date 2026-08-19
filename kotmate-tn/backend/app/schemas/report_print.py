import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.printing import PrintJobPayload

REPORT_PRINT_TYPES = [
    "sales-summary",
    "item-wise",
    "category-wise",
    "tax-summary",
    "waiter-wise",
    "cashier-wise",
    "waiter-incentive",
    "cashier-incentive",
    "pos-operator-wise",
    "pos-operator-incentive",
    "z-report",
]


class ReportPrintRequest(BaseModel):
    report_type: str
    # date_from/date_to for every report_type except z-report, which uses report_date
    # alone (same split as the existing GET endpoints/ReportsPage.tsx).
    date_from: date | None = None
    date_to: date | None = None
    report_date: date | None = None
    location_id: uuid.UUID | None = None


class ReportPrintingSettingsRequest(BaseModel):
    enabled: bool


class ReportPrintingSettingsResponse(BaseModel):
    enabled: bool


class ReportTamilNamesSettingsRequest(BaseModel):
    enabled: bool


class ReportTamilNamesSettingsResponse(BaseModel):
    enabled: bool


class ReportPrintResponse(BaseModel):
    printed: bool
    # usb/local_agent/bluetooth/rawbt printers only get rendered bytes back — see
    # PrintJobPayload — for the frontend to dispatch itself (printDispatch.ts).
    print_job: PrintJobPayload | None = None
    # Set only when a network/wifi reports printer was registered and the backend's
    # direct delivery attempt failed.
    print_error: str | None = None
