import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreateRequest(BaseModel):
    name_en: str = Field(min_length=1, max_length=100)
    name_ta: str | None = Field(default=None, max_length=100)
    # Appended after the current last category when omitted.
    display_order: int | None = None


class CategoryUpdateRequest(BaseModel):
    name_en: str | None = Field(default=None, min_length=1, max_length=100)
    name_ta: str | None = None
    display_order: int | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ta: str | None
    icon_url: str | None
    display_order: int
    is_active: bool
    created_at: datetime


class CategoryReorderEntry(BaseModel):
    id: uuid.UUID
    display_order: int


class CategoryReorderRequest(BaseModel):
    categories: list[CategoryReorderEntry]
