import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import LanguagePref, UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID | None
    store_id: uuid.UUID | None
    name: str
    email: EmailStr
    phone: str | None
    role: UserRole
    is_active: bool
    language_pref: LanguagePref


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8, max_length=72)
    role: UserRole
    store_id: uuid.UUID | None = None
    language_pref: LanguagePref = LanguagePref.EN

    @field_validator("role")
    @classmethod
    def role_must_not_be_product_owner(cls, value: UserRole) -> UserRole:
        if value == UserRole.PRODUCT_OWNER:
            raise ValueError("role must be admin or pos_user")
        return value


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    store_id: uuid.UUID | None = None
    is_active: bool | None = None
    language_pref: LanguagePref | None = None
