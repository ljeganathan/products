import uuid

from pydantic import BaseModel, ConfigDict, Field


class StockItemResponse(BaseModel):
    """One row for the KOT screen's Stock Management tab — every active item, any
    track_inventory state, since giving an item a quantity here turns tracking on.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ta: str | None
    category_id: uuid.UUID
    track_inventory: bool
    available_qty: int | None


class StockUpdateRequest(BaseModel):
    # None = stop tracking this item entirely (clears track_inventory + available_qty)
    # — saving the Stock Management tab's qty box blank, the reverse of giving it a
    # quantity turning tracking on.
    available_qty: int | None = Field(default=None, ge=0)


class StockManagementSettingsRequest(BaseModel):
    enabled: bool


class StockManagementSettingsResponse(BaseModel):
    enabled: bool
