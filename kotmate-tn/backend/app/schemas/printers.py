import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import PRINTER_CONNECTION_TYPES, PRINTER_TARGETS, PRINTER_TYPES


class PrinterCreateRequest(BaseModel):
    location_id: uuid.UUID
    name: str = Field(min_length=1, max_length=100)
    target: str
    printer_type: str
    connection_type: str
    connection_details: dict = Field(default_factory=dict)

    @field_validator("target")
    @classmethod
    def _target_valid(cls, v: str) -> str:
        if v not in PRINTER_TARGETS:
            raise ValueError(f"target must be one of {PRINTER_TARGETS}")
        return v

    @field_validator("printer_type")
    @classmethod
    def _printer_type_valid(cls, v: str) -> str:
        if v not in PRINTER_TYPES:
            raise ValueError(f"printer_type must be one of {PRINTER_TYPES}")
        return v

    @field_validator("connection_type")
    @classmethod
    def _connection_type_valid(cls, v: str) -> str:
        if v not in PRINTER_CONNECTION_TYPES:
            raise ValueError(f"connection_type must be one of {PRINTER_CONNECTION_TYPES}")
        return v


class PrinterUpdateRequest(BaseModel):
    location_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    target: str | None = None
    printer_type: str | None = None
    connection_type: str | None = None
    connection_details: dict | None = None
    is_active: bool | None = None

    @field_validator("target")
    @classmethod
    def _target_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in PRINTER_TARGETS:
            raise ValueError(f"target must be one of {PRINTER_TARGETS}")
        return v

    @field_validator("printer_type")
    @classmethod
    def _printer_type_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in PRINTER_TYPES:
            raise ValueError(f"printer_type must be one of {PRINTER_TYPES}")
        return v

    @field_validator("connection_type")
    @classmethod
    def _connection_type_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in PRINTER_CONNECTION_TYPES:
            raise ValueError(f"connection_type must be one of {PRINTER_CONNECTION_TYPES}")
        return v


class PrinterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    name: str
    target: str
    printer_type: str
    connection_type: str
    connection_details: dict
    is_active: bool
    created_at: datetime
