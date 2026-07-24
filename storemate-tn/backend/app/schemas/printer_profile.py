import uuid

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


class PrinterProfileCreate(BaseModel):
    store_id: uuid.UUID | None = None
    name: str
    type: PrinterType
    connection: PrinterConnection
    is_default: bool = False
    paper_width_chars: int = Field(gt=0)


class PrinterProfileUpdate(BaseModel):
    name: str | None = None
    type: PrinterType | None = None
    connection: PrinterConnection | None = None
    is_default: bool | None = None
    paper_width_chars: int | None = Field(default=None, gt=0)
