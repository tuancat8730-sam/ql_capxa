"""Software-delivery projects: the WBS schedule, the contractor's weekly reports and the open
decisions waiting for the investor (`wbs_tasks`, `weekly_reports`, `decision_items`)."""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

WBS_STATUSES = ("not_started", "in_progress", "done", "on_hold")
REPORT_STATUSES = ("received", "needs_more")
DECISION_STATUSES = ("pending", "decided", "not_applicable")


def _project_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)


class WbsTask(IdMixin, TimestampMixin, Base):
    """One line of the schedule: a task with a planned period, or a milestone (a single day).

    The phase it belongs to is stored on the line, so the schedule reads as one flat table.
    """

    __tablename__ = "wbs_tasks"
    __table_args__ = (
        UniqueConstraint("project_id", "code", name="wbs_tasks_project_code"),
        enum_check("status", WBS_STATUSES),
        CheckConstraint("pct BETWEEN 0 AND 100", name="pct_range"),
        Index("ix_wbs_tasks_project_order", "project_id", "sort_order"),
    )

    project_id: Mapped[uuid.UUID] = _project_fk()
    phase_code: Mapped[str] = mapped_column(String(10), nullable=False)
    phase_name: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plan_start: Mapped[date] = mapped_column(Date, nullable=False)
    plan_end: Mapped[date] = mapped_column(Date, nullable=False)
    # Working days: the weight of the line in every progress figure (0 for a milestone).
    plan_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # --- execution tracking; `tracked` stays false until someone records progress
    tracked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeeklyReport(IdMixin, TimestampMixin, Base):
    """The contractor's report for one 7-day period, identified by the day the period starts."""

    __tablename__ = "weekly_reports"
    __table_args__ = (
        UniqueConstraint("project_id", "week_start", name="weekly_reports_project_week"),
        enum_check("status", REPORT_STATUSES),
        CheckConstraint("planned_pct BETWEEN 0 AND 100", name="planned_range"),
        CheckConstraint("actual_pct BETWEEN 0 AND 100", name="actual_range"),
    )

    project_id: Mapped[uuid.UUID] = _project_fk()
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    report_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False)
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    link: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    done: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ids of the risks the report mentions
    risk_ids: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )


class DecisionItem(IdMixin, TimestampMixin, Base):
    """A matter the investor still has to decide ("tồn đọng chờ CĐT")."""

    __tablename__ = "decision_items"
    __table_args__ = (
        UniqueConstraint("project_id", "no", name="decision_items_project_no"),
        enum_check("status", DECISION_STATUSES),
    )

    project_id: Mapped[uuid.UUID] = _project_fk()
    no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_on: Mapped[date | None] = mapped_column(Date, nullable=True)
