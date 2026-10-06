"""`stage_plans` (SPEC 3.13), `tasks` (3.14) and `progress_logs` (3.15)."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, enum_check
from app.models.project import STAGE_CODES

STAGE_STATUSES = ("not_started", "in_progress", "done", "delayed", "blocked")
TASK_STATUSES = ("todo", "doing", "done", "blocked")
TASK_PRIORITIES = ("low", "normal", "high")

_PCT = Numeric(5, 2)


class StagePlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "stage_plans"
    __table_args__ = (
        UniqueConstraint("package_id", "stage_code", name="package_stage"),
        enum_check("stage_code", STAGE_CODES),
        enum_check("status", STAGE_STATUSES),
        CheckConstraint("progress_pct BETWEEN 0 AND 100", name="progress_range"),
        CheckConstraint("weight >= 0", name="weight_nonneg"),
    )

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    stage_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress_pct: Mapped[Decimal] = mapped_column(_PCT, default=0, nullable=False)
    weight: Mapped[Decimal] = mapped_column(_PCT, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Task(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        enum_check("status", TASK_STATUSES),
        enum_check("priority", TASK_PRIORITIES),
        Index("ix_tasks_package", "package_id"),
    )

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    stage_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stage_plans.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="todo", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    weight: Mapped[Decimal] = mapped_column(_PCT, default=1, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    depends_on: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False
    )


class ProgressLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "progress_logs"
    __table_args__ = (
        UniqueConstraint("package_id", "log_date", "author_id", name="package_date_author"),
        CheckConstraint("progress_pct BETWEEN 0 AND 100", name="progress_range"),
        Index(
            "uq_progress_logs_client_id",
            "client_id",
            unique=True,
            postgresql_where=text("client_id IS NOT NULL"),
        ),
    )

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=False
    )
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    progress_pct: Mapped[Decimal] = mapped_column(_PCT, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    workers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weather: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # List of document ids (photos uploaded through the document store).
    attachments: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    # Idempotency-Key from the offline queue (SPEC 15.7): a retried send never double-posts.
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
