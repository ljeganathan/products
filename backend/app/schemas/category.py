import uuid

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name_en: str
    name_ta: str
    parent_category_id: uuid.UUID | None
    hsn_code: str | None


class CategoryCreate(BaseModel):
    name_en: str
    name_ta: str
    parent_category_id: uuid.UUID | None = None
    hsn_code: str | None = None


class CategoryUpdate(BaseModel):
    name_en: str | None = None
    name_ta: str | None = None
    parent_category_id: uuid.UUID | None = None
    hsn_code: str | None = None
