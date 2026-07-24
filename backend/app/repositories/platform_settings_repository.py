from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform_settings import PlatformSettings


class PlatformSettingsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create(self) -> PlatformSettings:
        """Singleton row — created lazily on first access rather than via a
        migration data-seed, so a fresh dev DB works with no extra step."""
        settings = await self.db.scalar(select(PlatformSettings).limit(1))
        if settings is None:
            settings = PlatformSettings(maintenance_mode=False, maintenance_message=None)
            self.db.add(settings)
            await self.db.flush()
        return settings
