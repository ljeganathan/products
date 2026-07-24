import uuid

from pydantic import BaseModel, ConfigDict


class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    legal_name: str
    display_name: str
    address: str
    gstin: str | None
    fssai_no: str | None
    phone: str | None
    logo_url: str | None
    invoice_footer_text: str | None


class CompanySettingsUpdate(BaseModel):
    legal_name: str | None = None
    display_name: str | None = None
    address: str | None = None
    gstin: str | None = None
    fssai_no: str | None = None
    phone: str | None = None
    invoice_footer_text: str | None = None


class LogoUploadResponse(BaseModel):
    logo_url: str
