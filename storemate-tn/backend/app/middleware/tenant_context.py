import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import TokenError, decode_token
from app.models.enums import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login", auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: uuid.UUID
    tenant_id: uuid.UUID | None
    store_id: uuid.UUID | None
    role: UserRole


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    if token is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_token(token)
    except TokenError as exc:
        raise _unauthorized(str(exc)) from exc

    if payload.get("type") != "access":
        raise _unauthorized("Invalid token type")

    sub = payload.get("sub")
    role_value = payload.get("role")
    if sub is None or role_value is None:
        raise _unauthorized("Malformed token")

    try:
        user_id = uuid.UUID(sub)
        role = UserRole(role_value)
        tenant_id = uuid.UUID(payload["tenant_id"]) if payload.get("tenant_id") else None
        store_id = uuid.UUID(payload["store_id"]) if payload.get("store_id") else None
    except ValueError as exc:
        raise _unauthorized("Malformed token") from exc

    if role != UserRole.PRODUCT_OWNER and tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Token is missing a tenant scope"
        )

    return CurrentUser(user_id=user_id, tenant_id=tenant_id, store_id=store_id, role=role)
