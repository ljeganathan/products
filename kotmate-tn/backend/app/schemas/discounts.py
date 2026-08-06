import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.constants import DISCOUNT_TYPES


class DiscountRuleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str
    # Percentage off, used directly for flat_percent/coupon; item_level rules store no
    # value here since item_level discount amounts are entered ad hoc at bill time
    # (CLAUDE.md Phase 09 scope) — this is just the rule's label/eligibility, not a rate.
    value: float | None = Field(default=None, ge=0, le=100)
    coupon_code: str | None = Field(default=None, min_length=1, max_length=30)

    @field_validator("type")
    @classmethod
    def _type_valid(cls, v: str) -> str:
        if v not in DISCOUNT_TYPES:
            raise ValueError(f"type must be one of {DISCOUNT_TYPES}")
        return v

    @model_validator(mode="after")
    def _coupon_requires_code(self) -> "DiscountRuleCreateRequest":
        if self.type == "coupon" and not self.coupon_code:
            raise ValueError("coupon_code is required for type=coupon")
        if self.type != "coupon" and self.coupon_code:
            raise ValueError("coupon_code is only valid for type=coupon")
        return self


class DiscountRuleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    value: float | None = Field(default=None, ge=0, le=100)
    coupon_code: str | None = Field(default=None, min_length=1, max_length=30)
    is_active: bool | None = None


class DiscountRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: str
    value: float | None
    coupon_code: str | None
    is_active: bool
    created_at: datetime
