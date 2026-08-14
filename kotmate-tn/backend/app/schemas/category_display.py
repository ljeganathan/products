from pydantic import BaseModel


class CategoryDisplaySettingsRequest(BaseModel):
    show_tamil_categories: bool


class CategoryDisplaySettingsResponse(BaseModel):
    show_tamil_categories: bool
