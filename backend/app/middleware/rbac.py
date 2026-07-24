from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status

from app.middleware.tenant_context import CurrentUser, get_current_user
from app.models.enums import UserRole


def require_role(*roles: UserRole) -> Callable[..., Coroutine[Any, Any, CurrentUser]]:
    """Dependency factory enforcing the Role -> Access Matrix (CLAUDE.md §5)."""

    async def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return _dependency
