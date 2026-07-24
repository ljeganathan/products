from pydantic import BaseModel, ConfigDict


class PlatformSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    maintenance_mode: bool
    maintenance_message: str | None


class PlatformSettingsUpdate(BaseModel):
    maintenance_mode: bool | None = None
    maintenance_message: str | None = None


class MaintenanceStatusOut(BaseModel):
    """Public-shape subset of PlatformSettingsOut — what the app shell polls
    for every authenticated user, regardless of role, to decide whether to
    show the maintenance banner."""

    model_config = ConfigDict(from_attributes=True)

    maintenance_mode: bool
    maintenance_message: str | None
