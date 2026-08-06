import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from app.core.config import get_settings


class StorageBackend(ABC):
    """Abstracted so swapping local disk for S3/Azure Blob later touches only this
    file's concrete implementation, not every caller (CLAUDE.md §2).
    """

    @abstractmethod
    async def save(self, *, tenant_id: uuid.UUID, subfolder: str, filename: str, content: bytes) -> str:
        """Persists `content` and returns a URL the frontend can load it from."""


class LocalDiskStorage(StorageBackend):
    def __init__(self, base_dir: Path, url_prefix: str) -> None:
        self._base_dir = base_dir
        self._url_prefix = url_prefix.rstrip("/")

    async def save(self, *, tenant_id: uuid.UUID, subfolder: str, filename: str, content: bytes) -> str:
        dest_dir = self._base_dir / str(tenant_id) / subfolder
        dest_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(filename).suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{suffix}"
        (dest_dir / stored_name).write_bytes(content)

        return f"{self._url_prefix}/{tenant_id}/{subfolder}/{stored_name}"


def get_storage() -> StorageBackend:
    settings = get_settings()
    return LocalDiskStorage(base_dir=Path(settings.UPLOAD_DIR), url_prefix=settings.UPLOAD_URL_PREFIX)
