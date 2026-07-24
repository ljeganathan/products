from pydantic import BaseModel

from app.models.enums import LanguagePref


class LanguageSettingsOut(BaseModel):
    language_pref: LanguagePref


class LanguageSettingsUpdate(BaseModel):
    language_pref: LanguagePref
