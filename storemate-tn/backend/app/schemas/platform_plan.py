import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PlanCode


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: PlanCode
    name: str
    price_paise: int
    max_users: int
    max_stores: int
    max_printer_profiles: int
    low_stock_alerts: bool
    saved_bill_days: int
    features_json: dict
    is_active: bool


class PlanCreate(BaseModel):
    code: PlanCode
    name: str = Field(min_length=1, max_length=100)
    price_paise: int = Field(ge=0)
    max_users: int
    max_stores: int
    max_printer_profiles: int
    low_stock_alerts: bool = False
    saved_bill_days: int
    features_json: dict = Field(default_factory=dict)
    is_active: bool = True


class PlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    price_paise: int | None = Field(default=None, ge=0)
    max_users: int | None = None
    max_stores: int | None = None
    max_printer_profiles: int | None = None
    low_stock_alerts: bool | None = None
    saved_bill_days: int | None = None
    features_json: dict | None = None
    is_active: bool | None = None
