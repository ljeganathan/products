import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    settings = get_settings()
    material = (settings.PAYMENT_SECRETS_KEY or settings.JWT_SECRET).encode("utf-8")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"kotmate-payment-secrets:" + material).digest()))


def encrypt_secret(value: str) -> str:
    """Symmetric encryption for stored gateway credentials (Phase 28) — never store or
    return these in plain text.
    """
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return None
