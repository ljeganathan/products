import uuid

from pydantic import BaseModel, ConfigDict, Field


class TaxProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    cgst_pct: float
    sgst_pct: float
    igst_pct: float
    is_default: bool
    warning: str | None = None


class TaxProfileCreate(BaseModel):
    name: str
    cgst_pct: float = Field(default=0, ge=0, le=100)
    sgst_pct: float = Field(default=0, ge=0, le=100)
    igst_pct: float = Field(default=0, ge=0, le=100)
    is_default: bool = False


class TaxProfileUpdate(BaseModel):
    name: str | None = None
    cgst_pct: float | None = Field(default=None, ge=0, le=100)
    sgst_pct: float | None = Field(default=None, ge=0, le=100)
    igst_pct: float | None = Field(default=None, ge=0, le=100)
    is_default: bool | None = None
