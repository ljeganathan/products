import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# "new" is the ticket's own initial state, set at creation — never a valid target for
# this endpoint; kitchen staff only ever move a ticket forward to preparing/ready.
_SETTABLE_TICKET_STATUSES = ["preparing", "ready"]


class KotSendRequest(BaseModel):
    order_id: uuid.UUID


class KotSendResponse(BaseModel):
    id: uuid.UUID
    ticket_number: str
    order_id: uuid.UUID
    table_number: str | None
    section_name_en: str
    status: str
    printed: bool


class KotTicketStatusUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status_valid(cls, v: str) -> str:
        if v not in _SETTABLE_TICKET_STATUSES:
            raise ValueError(f"status must be one of {_SETTABLE_TICKET_STATUSES}")
        return v


class ActiveKotTicketItem(BaseModel):
    name_en: str
    name_ta: str | None
    quantity: int = Field(gt=0)


class ActiveKotTicketResponse(BaseModel):
    id: uuid.UUID
    ticket_number: str
    order_id: uuid.UUID
    table_number: str | None
    section_name_en: str
    status: str
    created_at: datetime
    items: list[ActiveKotTicketItem]
