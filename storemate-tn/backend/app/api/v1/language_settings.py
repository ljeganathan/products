from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.middleware.tenant_context import CurrentUser
from app.models.enums import UserRole
from app.repositories.user_repository import UserRepository
from app.schemas.language_settings import LanguageSettingsOut, LanguageSettingsUpdate

router = APIRouter(prefix="/settings/language", tags=["language-settings"])

require_admin = require_role(UserRole.ADMIN)

# CLAUDE.md §7 describes language as a per-tenant setting, but the schema
# (docs/DATABASE_SCHEMA.md) has no tenant-level language column — only
# users.language_pref. This operates on the calling admin's own
# language_pref, which is the practical stand-in: it's what actually drives
# the UI language on login (Phase 4), and is the only durable place to
# persist a "store default" without a schema change.


@router.get("", response_model=LanguageSettingsOut)
async def get_language_settings(
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LanguageSettingsOut:
    user = await UserRepository(db).get_by_id(current_user.user_id)
    assert user is not None
    return LanguageSettingsOut(language_pref=user.language_pref)


@router.patch("", response_model=LanguageSettingsOut)
async def update_language_settings(
    payload: LanguageSettingsUpdate,
    current_user: CurrentUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> LanguageSettingsOut:
    user = await UserRepository(db).get_by_id(current_user.user_id)
    assert user is not None
    user.language_pref = payload.language_pref
    await db.flush()
    await db.commit()
    return LanguageSettingsOut(language_pref=user.language_pref)
