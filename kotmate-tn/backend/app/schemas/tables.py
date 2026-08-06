import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TableCreateRequest(BaseModel):
    location_id: uuid.UUID
    # Required — only seating_sections with is_seating=true are selectable (CLAUDE.md
    # §9/§11); Takeaway/Online Delivery don't get table rows.
    section_id: uuid.UUID
    table_number: str = Field(min_length=1, max_length=20)
    seating_capacity: int | None = Field(default=None, gt=0)


class TableUpdateRequest(BaseModel):
    location_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    table_number: str | None = Field(default=None, min_length=1, max_length=20)
    seating_capacity: int | None = Field(default=None, gt=0)
    is_active: bool | None = None


class TableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    location_id: uuid.UUID
    section_id: uuid.UUID
    table_number: str
    seating_capacity: int | None
    # Driven by the POS/order flow (Phase 07+), not editable from this master screen.
    status: str
    is_active: bool
    created_at: datetime
