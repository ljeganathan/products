import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import DISCOUNT_MODES, DISCOUNT_TYPES


class DiscountRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str
    discount_mode: str = "percent"
    # percent: 0-100 (enforced below). rupee: any non-negative amount, capped against
    # the actual bill/line total at billing time (bill_service._rule_amount).
    value: float | None = Field(default=None, ge=0)
    # Only meaningful for type="item_level" — the specific item this rule discounts.
    item_id: uuid.UUID | None = None
    coupon_code: str | None = Field(default=None, min_length=1, max_length=30)
    expires_at: date | None = None

    @field_validator("type")
    @classmethod
    def _type_valid(cls, v: str) -> str:
        if v not in DISCOUNT_TYPES:
            raise ValueError(f"type must be one of {DISCOUNT_TYPES}")
        return v

    @field_validator("discount_mode")
    @classmethod
    def _mode_valid(cls, v: str) -> str:
        if v not in DISCOUNT_MODES:
            raise ValueError(f"discount_mode must be one of {DISCOUNT_MODES}")
        return v

    @model_validator(mode="after")
    def _shape_matches_type(self) -> "DiscountRuleCreateRequest":
        if self.type == "coupon" and not self.coupon_code:
            raise ValueError("coupon_code is required for type=coupon")
        if self.type != "coupon" and self.coupon_code:
            raise ValueError("coupon_code is only valid for type=coupon")
        if self.type == "item_level" and not self.item_id:
            raise ValueError("item_id is required for type=item_level")
        if self.type != "item_level" and self.item_id:
            raise ValueError("item_id is only valid for type=item_level")
        if self.discount_mode == "percent" and self.value is not None and self.value > 100:
            raise ValueError("value cannot exceed 100 when discount_mode=percent")
        return self


class DiscountRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    discount_mode: str | None = None
    value: float | None = Field(default=None, ge=0)
    item_id: uuid.UUID | None = None
    coupon_code: str | None = Field(default=None, min_length=1, max_length=30)
    expires_at: date | None = None
    is_active: bool | None = None

    @field_validator("discount_mode")
    @classmethod
    def _mode_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in DISCOUNT_MODES:
            raise ValueError(f"discount_mode must be one of {DISCOUNT_MODES}")
        return v


class DiscountRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    discount_mode: str
    value: float | None
    item_id: uuid.UUID | None
    item_name_en: str | None = None
    coupon_code: str | None
    expires_at: date | None
    is_active: bool
    created_at: datetime
