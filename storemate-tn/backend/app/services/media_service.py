import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings

_ALLOWED_LOGO_TYPES = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}


async def save_company_logo(file: UploadFile, *, tenant_id: uuid.UUID, store_id: uuid.UUID) -> str:
    """Saves the uploaded logo under MEDIA_ROOT/logos/<tenant_id>/<store_id>.<ext>
    and returns a URL servable via the /media static mount. Swap this
    function's body for an S3-compatible upload when scaling beyond a single
    Hostinger VPS — callers only ever see the returned URL string."""
    settings = get_settings()

    if file.content_type not in _ALLOWED_LOGO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logo must be a PNG, JPEG, or WEBP image",
        )

    contents = await file.read()
    max_bytes = settings.MAX_LOGO_UPLOAD_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logo exceeds the {settings.MAX_LOGO_UPLOAD_MB}MB size limit",
        )

    ext = _ALLOWED_LOGO_TYPES[file.content_type]
    logos_dir = Path(settings.MEDIA_ROOT) / "logos" / str(tenant_id)
    logos_dir.mkdir(parents=True, exist_ok=True)

    for existing in logos_dir.glob(f"{store_id}.*"):
        existing.unlink(missing_ok=True)

    filename = f"{store_id}{ext}"
    (logos_dir / filename).write_bytes(contents)

    return f"{settings.MEDIA_URL_PREFIX}/logos/{tenant_id}/{filename}"
