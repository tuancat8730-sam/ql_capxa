"""`guarantees` (SPEC 3.10), `payments` (3.11) and `disbursement_plan` (3.12)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, enum_check

GUARANTEE_TYPES = ("bid", "performance", "advance", "warranty")
GUARANTEE_STATUSES = ("pending", "valid", "expiring", "expired", "released", "missing")
PAYMENT_TYPES = ("advance", "payment", "recovery", "penalty")
PAYMENT_STATUSES = ("planned", "requested", "approved", "paid", "rejected")

_MONEY = Numeric(18, 0)


class Guarantee(IdMixin, TimestampMixin, Base):
    __tablename__ = "guarantees"
    __table_args__ = (
        enum_check("guarantee_type", GUARANTEE_TYPES),
        enum_check("status", GUARANTEE_STATUSES),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    provider_org_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    guarantee_type: Mapped[str] = mapped_column(String(20), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    guarantee_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    validity_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="valid", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # No FK yet: `documents` arrives in M4.
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verify_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        enum_check("payment_type", PAYMENT_TYPES),
        enum_check("status", PAYMENT_STATUSES),
        CheckConstraint("seq >= 0", name="seq_nonneg"),
    )

    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True
    )
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    requested_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    treasury_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisbursementPlan(IdMixin, TimestampMixin, Base):
    __tablename__ = "disbursement_plan"
    __table_args__ = (
        CheckConstraint("month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("year BETWEEN 2000 AND 2100", name="year_range"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    package_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("packages.id"), nullable=True
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_amount: Mapped[Decimal] = mapped_column(_MONEY, nullable=False)
    actual_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
