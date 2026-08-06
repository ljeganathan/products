import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SectionCreateRequest(BaseModel):
    name_en: str = Field(min_length=1, max_length=100)
    name_ta: str | None = Field(default=None, max_length=100)
    # True for AC/Non-AC/Rooftop/Family-style physical seating (table number required in
    # POS); false for Takeaway/Online Delivery (CLAUDE.md §9).
    is_seating: bool = True
    # Appended after the current last section when omitted.
    display_order: int | None = None


class SectionUpdateRequest(BaseModel):
    name_en: str | None = Field(default=None, min_length=1, max_length=100)
    name_ta: str | None = None
    is_seating: bool | None = None
    display_order: int | None = None
    is_active: bool | None = None


class SectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ta: str | None
    is_seating: bool
    display_order: int
    is_active: bool
    created_at: datetime


class SectionReorderEntry(BaseModel):
    id: uuid.UUID
    display_order: int


class SectionReorderRequest(BaseModel):
    sections: list[SectionReorderEntry]
