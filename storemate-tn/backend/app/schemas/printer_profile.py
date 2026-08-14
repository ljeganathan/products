import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PrinterConnection, PrinterType


class PrinterProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    name: str
    type: PrinterType
    connection: PrinterConnection
    is_default: bool
    paper_width_chars: int
    connection_details: dict[str, Any]


class PrinterProfileCreate(BaseModel):
    store_id: uuid.UUID | None = None
    name: str
    type: PrinterType
    connection: PrinterConnection
    is_default: bool = False
    paper_width_chars: int = Field(gt=0)
    connection_details: dict[str, Any] = Field(default_factory=dict)


class PrinterProfileUpdate(BaseModel):
    name: str | None = None
    type: PrinterType | None = None
    connection: PrinterConnection | None = None
    is_default: bool | None = None
    paper_width_chars: int | None = Field(default=None, gt=0)
    connection_details: dict[str, Any] | None = None


class PrinterNetworkPrintRequest(BaseModel):
    """Base64-encoded ESC/POS (thermal) or UTF-8 (dot-matrix) print job the
    frontend already rendered — see utils.network_print's docstring for why
    network/WiFi printers are the one connection type dispatched from the
    backend instead of the browser."""

    data_base64: str = Field(min_length=1)
