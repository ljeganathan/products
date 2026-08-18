from pydantic import BaseModel, field_validator

from app.core.constants import PAYMENT_METHODS


class DefaultPaymentMethodRequest(BaseModel):
    default_payment_method: str

    @field_validator("default_payment_method")
    @classmethod
    def _method_valid(cls, v: str) -> str:
        if v not in PAYMENT_METHODS:
            raise ValueError(f"default_payment_method must be one of {PAYMENT_METHODS}")
        return v


class DefaultPaymentMethodResponse(BaseModel):
    default_payment_method: str
