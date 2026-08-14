import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

PINCODE_PATTERN = re.compile(r"^[1-9][0-9]{5}$")


class CompanySettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    legal_name: str
    display_name: str
    address: str
    pincode: str | None
    gstin: str | None
    fssai_no: str | None
    phone: str | None
    logo_url: str | None
    invoice_footer_text: str | None
    show_tamil_item_names: bool
    upi_vpa: str | None
    show_upi_qr: bool


class CompanySettingsUpdate(BaseModel):
    legal_name: str | None = None
    display_name: str | None = None
    address: str | None = None
    pincode: str | None = None
    gstin: str | None = None
    fssai_no: str | None = None
    phone: str | None = None
    invoice_footer_text: str | None = None
    show_tamil_item_names: bool | None = None
    upi_vpa: str | None = None
    show_upi_qr: bool | None = None

    @field_validator("pincode")
    @classmethod
    def pincode_must_be_valid(cls, value: str | None) -> str | None:
        if value is None or value == "":
            raise ValueError("Pincode is required")
        if not PINCODE_PATTERN.match(value):
            raise ValueError("Pincode must be a valid 6-digit Indian PIN code")
        return value


class LogoUploadResponse(BaseModel):
    logo_url: str
