"""`audit_log` table (SPEC 3.24, 4.18). Append-only: no update/delete paths exist."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin

AUDIT_ACTIONS = ("create", "update", "delete", "login", "download", "export")


class AuditLog(IdMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        CheckConstraint(
            "action IN ('create','update','delete','login','download','export')", name="action"
        ),
        Index("ix_audit_log_ts", "ts"),
        Index("ix_audit_log_project", "project_id"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
    )

    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # NULL for events that belong to no project (login, user admin).
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
