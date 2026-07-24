from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.tenant_context import CurrentUser, get_current_user
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AccessTokenResponse, LoginRequest, RefreshRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import auth_service
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    access_token, refresh_token = auth_service.issue_tokens(user)

    await record_audit_log(
        db,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login",
        entity="user",
        entity_id=user.id,
    )
    await db.commit()

    return TokenResponse(
        access_token=access_token, refresh_token=refresh_token, user=UserOut.model_validate(user)
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    payload: RefreshRequest, db: AsyncSession = Depends(get_db)
) -> AccessTokenResponse:
    access_token = await auth_service.refresh_access_token(db, payload.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: CurrentUser = Depends(get_current_user)) -> None:
    # Stateless JWT: no refresh-token/session store exists in this schema
    # (see docs/DATABASE_SCHEMA.md), so there is nothing to revoke server-side.
    # The client is expected to discard both tokens.
    return None


@router.get("/me", response_model=UserOut)
async def me(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> UserOut:
    repo = UserRepository(db)
    user = await repo.get_by_id(current_user.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)
