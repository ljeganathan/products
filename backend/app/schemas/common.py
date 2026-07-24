from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class UsageOut(BaseModel):
    """A tenant's current usage vs its plan's limits. `*_limit == -1` means
    unlimited (matches the `plans` table's UNLIMITED sentinel)."""

    users_count: int
    users_limit: int
    stores_count: int
    stores_limit: int
    printer_profiles_count: int
    printer_profiles_limit: int
