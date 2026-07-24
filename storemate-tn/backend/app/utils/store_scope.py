import uuid

from fastapi import HTTPException, status

from app.middleware.tenant_context import CurrentUser


def resolve_store_id(current_user: CurrentUser, explicit_store_id: uuid.UUID | None) -> uuid.UUID:
    """Store-scoped resources (items, stock, settings) need a concrete
    store_id. Most users (pos_user, single-store admin) already carry one on
    their token; a multi-store admin (Pro Max) must pass it explicitly."""
    store_id = explicit_store_id or current_user.store_id
    if store_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="store_id is required (your account is not scoped to a single default store)",
        )
    return store_id
