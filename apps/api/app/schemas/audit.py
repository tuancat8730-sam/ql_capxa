import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    user_id: uuid.UUID | None
    user_name: str | None = None
    action: str
    entity_type: str
    entity_id: str | None
    changes: dict[str, Any] | None
    ip: str | None
    user_agent: str | None


class AuditUser(BaseModel):
    id: uuid.UUID
    name: str


class AuditFacets(BaseModel):
    """Values that exist in the log, for the filter drop-downs of the audit viewer."""

    actions: list[str]
    entity_types: list[str]
    users: list[AuditUser]
