import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemCreateRequest(BaseModel):
    name_en: str = Field(min_length=1, max_length=150)
    name_ta: str | None = Field(default=None, max_length=150)
    category_id: uuid.UUID
    price: float = Field(gt=0)
    tax_class_id: uuid.UUID | None = None
    item_code: str | None = Field(default=None, max_length=20)
    is_top_seller: bool = False
    is_combo_tile: bool = False
    track_inventory: bool = False
    # Only meaningful when track_inventory=True (CLAUDE.md §11) — set here or later via
    # PATCH /items/{id}/restock.
    available_qty: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _available_qty_requires_tracking(self) -> "ItemCreateRequest":
        if self.available_qty is not None and not self.track_inventory:
            raise ValueError("available_qty can only be set when track_inventory=true")
        return self


class ItemUpdateRequest(BaseModel):
    name_en: str | None = Field(default=None, min_length=1, max_length=150)
    name_ta: str | None = None
    category_id: uuid.UUID | None = None
    price: float | None = Field(default=None, gt=0)
    tax_class_id: uuid.UUID | None = None
    item_code: str | None = None
    is_top_seller: bool | None = None
    is_combo_tile: bool | None = None
    track_inventory: bool | None = None
    available_qty: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class RestockRequest(BaseModel):
    available_qty: int = Field(ge=0)


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ta: str | None
    category_id: uuid.UUID
    price: float
    tax_class_id: uuid.UUID | None
    item_code: str | None
    image_url: str | None
    is_top_seller: bool
    is_combo_tile: bool
    track_inventory: bool
    available_qty: int | None
    is_active: bool
    created_at: datetime


class SectionPriceOption(BaseModel):
    section_id: uuid.UUID
    section_name_en: str
    override_price: float | None
    resolved_price: float


class SectionPriceEntry(BaseModel):
    section_id: uuid.UUID
    # null clears any existing override for that section, falling back to base price.
    price: float | None = Field(default=None, gt=0)


class SectionPriceUpdateRequest(BaseModel):
    prices: list[SectionPriceEntry]


class ItemImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
