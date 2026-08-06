import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaxRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    cgst_rate: float = Field(ge=0, le=100)
    sgst_rate: float = Field(ge=0, le=100)
    is_default: bool = False


class TaxRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    cgst_rate: float | None = Field(default=None, ge=0, le=100)
    sgst_rate: float | None = Field(default=None, ge=0, le=100)
    is_default: bool | None = None
    is_active: bool | None = None


class TaxRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    cgst_rate: float
    sgst_rate: float
    is_default: bool
    is_active: bool
    created_at: datetime
