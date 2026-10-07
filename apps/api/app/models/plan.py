"""Delivery plan of a package: `package_plans`, `plan_items` (equipment) and `plan_steps`.

One current plan per package; it is read from the contractor's plan document (.docx or .doc) and
replaced when a new version is uploaded. Steps carry the tracking of the execution.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

PLAN_STEP_STATUSES = ("not_started", "in_progress", "done", "blocked")


class PackagePlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "package_plans"

    package_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), unique=True, nullable=False
    )
    addressee: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_basis: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    implement_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    implement_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    implement_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # [{"label": "...", "text": "..."}]
    locations: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    signer: Mapped[str | None] = mapped_column(Text, nullable=True)
    declared_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class PlanItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_items"
    __table_args__ = (Index("ix_plan_items_plan", "plan_id"),)

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("package_plans.id", ondelete="CASCADE"), nullable=False
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # [{"org": "...", "quantity": 3 | null}]
    assignments: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlanStep(IdMixin, TimestampMixin, Base):
    __tablename__ = "plan_steps"
    __table_args__ = (
        enum_check("status", PLAN_STEP_STATUSES),
        Index("ix_plan_steps_plan", "plan_id"),
    )

    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("package_plans.id", ondelete="CASCADE"), nullable=False
    )
    group_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    group_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # fingerprint of the content: ties a step to its older version when a plan is replaced
    content_hash: Mapped[str] = mapped_column(String(40), nullable=False)
    time_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    time_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    # --- execution tracking ---
    status: Mapped[str] = mapped_column(String(20), default="not_started", nullable=False)
    actual_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    tracking_note: Mapped[str | None] = mapped_column(Text, nullable=True)
