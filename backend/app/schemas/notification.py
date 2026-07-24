import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import NotificationType


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    store_id: uuid.UUID
    type: NotificationType
    title: str
    body: str
    is_read: bool
    created_for_user_id: uuid.UUID | None
    reference_id: uuid.UUID | None
    created_at: datetime
