"""Construction logs of a software-delivery project: the contractor's weekly site diary.

One log per reporting week (`construction_logs`, keyed like `weekly_reports` by the day the
period starts) with three kinds of lines: the day-by-day events (`construction_log_entries`),
the carry-over table for next week (`construction_log_carryovers`) and the part of work done by
a consortium member (`construction_log_member_work`). Lines may point at a WBS task by its code.
"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

ENTRY_STATES = ("not_started", "in_progress", "done", "blocked")


def _log_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("construction_logs.id", ondelete="CASCADE"), nullable=False
    )


def _personnel() -> Mapped[list[Any]]:
    return mapped_column(JSONB, default=list, server_default="[]", nullable=False)


class ConstructionLog(IdMixin, TimestampMixin, Base):
    __tablename__ = "construction_logs"
    __table_args__ = (UniqueConstraint("project_id", "week_start", name="construction_logs_week"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    recipients: Mapped[str | None] = mapped_column(Text, nullable=True)
    reporter_org: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contract_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    coordinator: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Only the later form of the log carries it.
    environment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    overall_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_results: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues: Mapped[str | None] = mapped_column(Text, nullable=True)
    coordination_requests: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_report: Mapped[str | None] = mapped_column(Text, nullable=True)

    entries: Mapped[list["ConstructionLogEntry"]] = relationship(
        back_populates="log",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="(ConstructionLogEntry.entry_date, ConstructionLogEntry.seq)",
    )
    carryovers: Mapped[list["ConstructionLogCarryover"]] = relationship(
        back_populates="log",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConstructionLogCarryover.seq",
    )
    member_work: Mapped[list["ConstructionLogMemberWork"]] = relationship(
        back_populates="log",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConstructionLogMemberWork.seq",
    )


class ConstructionLogEntry(IdMixin, Base):
    """What happened on one day, under one phase of the schedule."""

    __tablename__ = "construction_log_entries"
    __table_args__ = (
        enum_check("state", ENTRY_STATES),
        CheckConstraint("delay_days >= 0", name="delay_days_range"),
        Index("ix_construction_log_entries_order", "log_id", "entry_date", "seq"),
        Index("ix_construction_log_entries_task", "task_code"),
    )

    log_id: Mapped[uuid.UUID] = _log_fk()
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_code: Mapped[str] = mapped_column(String(10), nullable=False)
    # `wbs_tasks.code` of the project; empty when the line covers several tasks.
    task_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    personnel: Mapped[list[Any]] = _personnel()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    log: Mapped[ConstructionLog] = relationship(back_populates="entries")


class ConstructionLogCarryover(IdMixin, Base):
    """A row of the "công việc chuyển tiếp" table: where a task stands and what comes next."""

    __tablename__ = "construction_log_carryovers"
    __table_args__ = (Index("ix_construction_log_carryovers_order", "log_id", "seq"),)

    log_id: Mapped[uuid.UUID] = _log_fk()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_code: Mapped[str] = mapped_column(String(10), nullable=False)
    task_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    result_to_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_week: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    log: Mapped[ConstructionLog] = relationship(back_populates="carryovers")


class ConstructionLogMemberWork(IdMixin, Base):
    """The part of the work a consortium member reports on its own."""

    __tablename__ = "construction_log_member_work"
    __table_args__ = (Index("ix_construction_log_member_work_order", "log_id", "seq"),)

    log_id: Mapped[uuid.UUID] = _log_fk()
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    member_name: Mapped[str] = mapped_column(String(200), nullable=False)
    item: Mapped[str] = mapped_column(Text, nullable=False)
    plan_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    personnel: Mapped[list[Any]] = _personnel()
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    issues_actions: Mapped[str | None] = mapped_column(Text, nullable=True)

    log: Mapped[ConstructionLog] = relationship(back_populates="member_work")
