import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ItemUnit


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    category_id: uuid.UUID
    name_en: str
    name_ta: str
    sku: str | None
    barcode: str | None
    unit: ItemUnit
    mrp_paise: int
    selling_price_paise: int
    cost_price_paise: int
    tax_profile_id: uuid.UUID
    reorder_level: float
    reorder_qty: float
    is_active: bool
    brand: str | None
    pack_size: str | None
    hsn_code: str | None
    batch_tracked: bool


class ItemCreate(BaseModel):
    category_id: uuid.UUID
    store_id: uuid.UUID | None = None
    name_en: str
    name_ta: str
    sku: str | None = None
    barcode: str | None = None
    unit: ItemUnit
    mrp_paise: int = Field(ge=0)
    selling_price_paise: int = Field(ge=0)
    cost_price_paise: int = Field(ge=0)
    tax_profile_id: uuid.UUID
    reorder_level: float = Field(default=0, ge=0)
    reorder_qty: float = Field(default=0, ge=0)
    brand: str | None = None
    pack_size: str | None = None
    hsn_code: str | None = None
    batch_tracked: bool = False
    opening_stock: float = Field(default=0, ge=0)


class ItemUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    name_en: str | None = None
    name_ta: str | None = None
    sku: str | None = None
    barcode: str | None = None
    unit: ItemUnit | None = None
    mrp_paise: int | None = Field(default=None, ge=0)
    selling_price_paise: int | None = Field(default=None, ge=0)
    cost_price_paise: int | None = Field(default=None, ge=0)
    tax_profile_id: uuid.UUID | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    reorder_qty: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    brand: str | None = None
    pack_size: str | None = None
    hsn_code: str | None = None
    batch_tracked: bool | None = None


class BulkImportRowError(BaseModel):
    row_number: int
    errors: list[str]


class BulkImportResult(BaseModel):
    total_rows: int
    created_count: int
    error_count: int
    errors: list[BulkImportRowError]
