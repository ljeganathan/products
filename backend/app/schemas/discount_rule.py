import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import DiscountScope, DiscountType


class DiscountRuleCreate(BaseModel):
    scope: DiscountScope
    # item.id or category.id depending on scope; must be null when scope=bill.
    target_id: uuid.UUID | None = None
    type: DiscountType
    # paise for flat, basis points for percent (10.50% -> 1050) — same
    # convention as bills' discount_value.
    value: int = Field(gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def _validate_target(self) -> "DiscountRuleCreate":
        if self.scope == DiscountScope.BILL and self.target_id is not None:
            raise ValueError("target_id must be omitted when scope is 'bill'")
        if self.scope != DiscountScope.BILL and self.target_id is None:
            raise ValueError("target_id is required when scope is 'item' or 'category'")
        return self


class DiscountRuleUpdate(BaseModel):
    type: DiscountType | None = None
    value: int | None = Field(default=None, gt=0)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool | None = None


class DiscountRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    scope: DiscountScope
    target_id: uuid.UUID | None
    type: DiscountType
    value: int
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
