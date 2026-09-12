import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StockCalcUnit = Literal["g", "kg", "ml", "l", "pcs"]


class StockItemResponse(BaseModel):
    """One row for the Stock Management screen — every active item, any
    track_inventory state, since giving an item a quantity here turns tracking on.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name_en: str
    name_ta: str | None
    category_id: uuid.UUID
    track_inventory: bool
    available_qty: int | None
    # The "Calculate for Me" popup's remembered per-item conversion (e.g. "500 g used
    # per Chicken Biryani") — null until that calculator has been used for this item at
    # least once, in which case the popup pre-fills these instead of asking again.
    stock_calc_qty: float | None
    stock_calc_unit: StockCalcUnit | None


class StockUpdateRequest(BaseModel):
    # None = stop tracking this item entirely (clears track_inventory + available_qty)
    # — saving the Stock Management tab's qty box blank, the reverse of giving it a
    # quantity turning tracking on.
    available_qty: int | None = Field(default=None, ge=0)
    # Set together whenever the "Calculate for Me" popup was used for this add — both
    # omitted (default None) leaves whatever was already remembered untouched, so a
    # plain "Type Amount" save never wipes out an earlier calculator entry.
    stock_calc_qty: float | None = Field(default=None, gt=0)
    stock_calc_unit: StockCalcUnit | None = None


class StockManagementSettingsRequest(BaseModel):
    enabled: bool


class StockManagementSettingsResponse(BaseModel):
    enabled: bool
