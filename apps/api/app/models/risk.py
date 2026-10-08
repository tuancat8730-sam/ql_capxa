"""Risks (SPEC 3.16), issues (3.17), meetings/actions (3.20), change requests (3.21), holidays."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

RISK_CATEGORIES = ("schedule", "cost", "quality", "legal", "contract", "supply", "safety", "other")
RISK_STATUSES = ("open", "mitigating", "occurred", "closed")
RISK_SOURCES = ("de_cuong", "analysis", "manual")
ISSUE_TYPES = ("operational", "contract", "schedule", "investor_request", "other")
ISSUE_STATUSES = ("open", "in_progress", "escalated", "resolved", "closed")
ISSUE_EVENTS = (
    "created",
    "escalated",
    "resolved",
    "reopened",
    "closed",
    "due_changed",
    "assigned",
    "status_changed",
)
MEETING_TYPES = ("kickoff", "package_kickoff", "weekly", "issue_resolution", "other")
ACTION_STATUSES = ("open", "done", "cancelled")
CHANGE_TYPES = ("model", "origin", "allocation", "schedule", "other")
CHANGE_STATUSES = ("proposed", "reviewing", "approved", "rejected", "appendix_signed")


def _fk(table: str, *, nullable: bool = True, ondelete: str | None = None) -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(f"{table}.id", ondelete=ondelete), nullable=nullable
    )


class Risk(IdMixin, TimestampMixin, Base):
    __tablename__ = "risks"
    __table_args__ = (
        enum_check("category", RISK_CATEGORIES),
        enum_check("status", RISK_STATUSES),
        enum_check("source", RISK_SOURCES),
        CheckConstraint("probability BETWEEN 1 AND 5", name="probability_range"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="impact_range"),
        CheckConstraint("score = probability * impact", name="score_matches"),
        Index("ix_risks_package", "package_id"),
        UniqueConstraint("project_id", "code", name="risks_project_code"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    project_id: Mapped[uuid.UUID] = _fk("projects", nullable=False)
    package_id: Mapped[uuid.UUID | None] = _fk("packages")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, nullable=False)
    impact: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = _fk("users")
    mitigation: Mapped[str | None] = mapped_column(Text, nullable=True)
    contingency: Mapped[str | None] = mapped_column(Text, nullable=True)
    # free-text fields of software-delivery projects (a theme, the party in charge, a running log)
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    owner_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Issue(IdMixin, TimestampMixin, Base):
    __tablename__ = "issues"
    __table_args__ = (
        enum_check("issue_type", ISSUE_TYPES),
        enum_check("status", ISSUE_STATUSES),
        CheckConstraint("level IN (1, 2, 3)", name="level_range"),
        Index("ix_issues_package", "package_id"),
        UniqueConstraint("project_id", "code", name="issues_project_code"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    project_id: Mapped[uuid.UUID] = _fk("projects", nullable=False)
    package_id: Mapped[uuid.UUID | None] = _fk("packages")
    issue_type: Mapped[str] = mapped_column(String(30), nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by: Mapped[uuid.UUID] = _fk("users", nullable=False)
    assigned_to: Mapped[uuid.UUID | None] = _fk("users")
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IssueEvent(IdMixin, Base):
    """History of an issue: creation, escalations, due-date changes (SPEC 4.9)."""

    __tablename__ = "issue_events"
    __table_args__ = (enum_check("event", ISSUE_EVENTS), Index("ix_issue_events_issue", "issue_id"))

    issue_id: Mapped[uuid.UUID] = _fk("issues", nullable=False, ondelete="CASCADE")
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = _fk("users")
    event: Mapped[str] = mapped_column(String(20), nullable=False)
    from_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Holiday(IdMixin, TimestampMixin, Base):
    """Non-working days used by the level-2 issue deadline (SPEC 7.4)."""

    __tablename__ = "holidays"

    day: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Meeting(IdMixin, TimestampMixin, Base):
    __tablename__ = "meetings"
    __table_args__ = (enum_check("meeting_type", MEETING_TYPES),)

    project_id: Mapped[uuid.UUID] = _fk("projects", nullable=False)
    package_id: Mapped[uuid.UUID | None] = _fk("packages")
    meeting_type: Mapped[str] = mapped_column(String(30), nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    chair: Mapped[str | None] = mapped_column(String(200), nullable=True)
    attendees: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    minutes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class ActionItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "action_items"
    __table_args__ = (enum_check("status", ACTION_STATUSES),)

    meeting_id: Mapped[uuid.UUID | None] = _fk("meetings", ondelete="CASCADE")
    package_id: Mapped[uuid.UUID | None] = _fk("packages")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = _fk("users")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)


class ChangeRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "change_requests"
    __table_args__ = (
        enum_check("change_type", CHANGE_TYPES),
        enum_check("status", CHANGE_STATUSES),
        UniqueConstraint("project_id", "code", name="change_requests_project_code"),
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    project_id: Mapped[uuid.UUID] = _fk("projects", nullable=False)
    package_id: Mapped[uuid.UUID] = _fk("packages", nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_by_org_id: Mapped[uuid.UUID | None] = _fk("organizations")
    supervisor_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    tvqlda_opinion: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = _fk("users")
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    amendment_id: Mapped[uuid.UUID | None] = _fk("contract_amendments")
