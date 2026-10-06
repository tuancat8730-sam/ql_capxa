import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    user_id: uuid.UUID | None
    action: str
    entity_type: str
    entity_id: str | None
    changes: dict[str, Any] | None
    ip: str | None
    user_agent: str | None
