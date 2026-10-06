"""`contracts` and children (SPEC 3.5, 3.7, 3.8, 3.9)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin, enum_check

CONTRACT_TYPES = ("lump_sum", "unit_price")
PENALTY_UNITS = ("day", "week")
CONTRACT_STATUSES = ("draft", "signed", "executing", "accepted", "liquidated", "terminated")
PARTY_ROLES = ("lead", "member", "sole")
AMENDMENT_TYPES = ("duration", "value", "scope", "other")

_MONEY = Numeric(18, 0)
_PCT = Numeric(5, 2)


def _fk(table: str, *, nullable: bool = False, cascade: bool = False) -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(f"{table}.id", ondelete="CASCADE" if cascade else None),
        nullable=nullable,
    )


class Contract(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "contracts"
    __table_args__ = (
        enum_check("contract_type", CONTRACT_TYPES),
        enum_check("penalty_unit", PENALTY_UNITS),
        enum_check("status", CONTRACT_STATUSES),
    )

    package_id: Mapped[uuid.UUID] = _fk("packages")
    contract_no: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    extended_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    contract_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    price_adjustment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    advance_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    advance_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    advance_recovery_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    performance_bond_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    performance_bond_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    warranty_bond_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    warranty_bond_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    penalty_rate_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    penalty_unit: Mapped[str | None] = mapped_column(String(10), nullable=True)
    penalty_cap_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    payment_terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_term_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    copies_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    investor_signer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    investor_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="signed", nullable=False)
    # No FK yet: `documents` arrives in M4.
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    data_quality_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContractParty(IdMixin, TimestampMixin, Base):
    __tablename__ = "contract_parties"
    __table_args__ = (enum_check("role", PARTY_ROLES),)

    contract_id: Mapped[uuid.UUID] = _fk("contracts", cascade=True)
    organization_id: Mapped[uuid.UUID] = _fk("organizations")
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    share_pct: Mapped[Decimal | None] = mapped_column(_PCT, nullable=True)
    share_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    advance_amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    bank_account: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContractItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "contract_items"

    contract_id: Mapped[uuid.UUID] = _fk("contracts", cascade=True)
    member_org_id: Mapped[uuid.UUID | None] = _fk("organizations", nullable=True)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 3), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_calibration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    origin: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContractAmendment(IdMixin, TimestampMixin, Base):
    __tablename__ = "contract_amendments"
    __table_args__ = (enum_check("type", AMENDMENT_TYPES),)

    contract_id: Mapped[uuid.UUID] = _fk("contracts", cascade=True)
    amendment_no: Mapped[str] = mapped_column(String(50), nullable=False)
    signed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[Decimal | None] = mapped_column(_MONEY, nullable=True)
    new_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
