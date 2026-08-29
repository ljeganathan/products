from pydantic import BaseModel, field_validator

from app.core.constants import POS_LAYOUTS


class PosLayoutSettingsRequest(BaseModel):
    pos_layout: str

    @field_validator("pos_layout")
    @classmethod
    def _layout_valid(cls, v: str) -> str:
        if v not in POS_LAYOUTS:
            raise ValueError(f"pos_layout must be one of {POS_LAYOUTS}")
        return v


class PosLayoutSettingsResponse(BaseModel):
    pos_layout: str


class WaiterMandatorySettingsRequest(BaseModel):
    enabled: bool


class WaiterMandatorySettingsResponse(BaseModel):
    enabled: bool
