import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

AlertSeverity = Literal["info", "warning", "critical"]
AlertStatus = Literal["open", "acknowledged", "resolved", "suppressed"]
MAX_SNOOZE_DAYS = 7  # SPEC 7.1

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    alert_type: str
    severity: AlertSeverity
    entity_type: str
    entity_id: str
    package_id: uuid.UUID | None
    package_number: int | None = None
    title: str
    message: str
    due_date: date | None
    status: AlertStatus
    assigned_to: uuid.UUID | None
    first_seen_at: datetime
    resolved_at: datetime | None
    acknowledged_by: uuid.UUID | None
    acknowledged_at: datetime | None
    snoozed_until: datetime | None
    snooze_reason: str | None
    can_snooze: bool = True


class AlertCounts(BaseModel):
    critical: int = 0
    warning: int = 0
    info: int = 0
    total: int = 0


class AlertAssign(BaseModel):
    assigned_to: uuid.UUID | None = None


class AlertSnooze(BaseModel):
    days: int = Field(ge=1, le=MAX_SNOOZE_DAYS)
    reason: Reason


class RefreshOut(BaseModel):
    created: int
    updated: int
    reopened: int
    resolved: int
    health_changed: int
    emails_sent: int
