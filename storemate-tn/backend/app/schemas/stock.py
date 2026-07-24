import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StockMovementReason


class StockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    item_id: uuid.UUID
    item_name_en: str
    item_name_ta: str
    barcode: str | None
    batch_no: str | None
    expiry_date: date | None
    quantity_on_hand: float
    reorder_level: float
    low_stock: bool
    last_restocked_at: datetime | None


class StockAdjustRequest(BaseModel):
    item_id: uuid.UUID
    store_id: uuid.UUID | None = None
    change_qty: float = Field(description="Positive to add stock, negative to remove")
    reason: StockMovementReason
    reference_id: uuid.UUID | None = None

    def model_post_init(self, __context: object) -> None:
        if self.change_qty == 0:
            raise ValueError("change_qty must not be zero")


class StockMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    item_id: uuid.UUID
    change_qty: float
    reason: StockMovementReason
    reference_id: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
