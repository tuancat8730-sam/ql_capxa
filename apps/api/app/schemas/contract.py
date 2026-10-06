import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import Money, Number, Percent

ContractType = Literal["lump_sum", "unit_price"]
ContractStatus = Literal["draft", "signed", "executing", "accepted", "liquidated", "terminated"]
PartyRole = Literal["lead", "member", "sole"]
AmendmentType = Literal["duration", "value", "scope", "other"]
PenaltyUnit = Literal["day", "week"]


class ContractUpdate(BaseModel):
    """Every field optional; only the fields sent are changed."""

    contract_no: str | None = Field(default=None, min_length=1, max_length=50)
    signed_date: date | None = None
    effective_date: date | None = None
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    planned_end_date: date | None = None
    extended_end_date: date | None = None
    end_date_override: bool | None = None
    contract_type: ContractType | None = None
    price_adjustment: bool | None = None
    value: Money | None = None
    advance_pct: Percent | None = None
    advance_amount: Money | None = None
    advance_recovery_note: str | None = None
    performance_bond_pct: Percent | None = None
    performance_bond_amount: Money | None = None
    warranty_bond_pct: Percent | None = None
    warranty_bond_amount: Money | None = None
    penalty_rate_pct: Percent | None = None
    penalty_unit: PenaltyUnit | None = None
    penalty_cap_pct: Percent | None = None
    payment_terms_text: str | None = None
    payment_term_days: int | None = Field(default=None, ge=0, le=365)
    copies_text: str | None = None
    investor_signer: str | None = Field(default=None, max_length=200)
    investor_account: str | None = Field(default=None, max_length=50)
    status: ContractStatus | None = None
    data_quality_note: str | None = None


class ContractCreate(ContractUpdate):
    """Same fields as an update, but the contract number is mandatory."""

    contract_no: str = Field(min_length=1, max_length=50)


class IssueOut(BaseModel):
    code: str
    severity: Literal["warning", "info"]
    message: str
    expected: str | None = None
    actual: str | None = None


class PartyIn(BaseModel):
    organization_id: uuid.UUID
    role: PartyRole
    share_pct: Percent | None = None
    share_amount: Money | None = None
    advance_amount: Money | None = None
    bank_account: str | None = Field(default=None, max_length=50)
    bank_name: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class PartyUpdate(BaseModel):
    role: PartyRole | None = None
    share_pct: Percent | None = None
    share_amount: Money | None = None
    advance_amount: Money | None = None
    bank_account: str | None = Field(default=None, max_length=50)
    bank_name: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class PartyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    organization_id: uuid.UUID
    organization_name: str | None = None
    role: PartyRole
    share_pct: Number | None
    share_amount: Number | None
    advance_amount: Number | None
    bank_account: str | None
    bank_name: str | None
    notes: str | None


class ItemUpdate(BaseModel):
    line_no: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1)
    member_org_id: uuid.UUID | None = None
    unit: str | None = Field(default=None, max_length=50)
    quantity: Number | None = Field(default=None, ge=0)
    unit_price: Money | None = None
    amount: Money | None = None
    warranty_months: int | None = Field(default=None, ge=0, le=600)
    requires_calibration: bool | None = None
    origin: str | None = Field(default=None, max_length=200)
    notes: str | None = None


class ItemIn(ItemUpdate):
    line_no: int = Field(ge=1)
    name: str = Field(min_length=1)


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    member_org_id: uuid.UUID | None
    line_no: int
    name: str
    unit: str | None
    quantity: Number | None
    unit_price: Number | None
    amount: Number | None
    warranty_months: int | None
    requires_calibration: bool
    origin: str | None
    notes: str | None


class AmendmentUpdate(BaseModel):
    amendment_no: str | None = Field(default=None, min_length=1, max_length=50)
    signed_date: date | None = None
    type: AmendmentType | None = None
    description: str | None = None
    new_value: Money | None = None
    new_end_date: date | None = None


class AmendmentIn(AmendmentUpdate):
    amendment_no: str = Field(min_length=1, max_length=50)
    type: AmendmentType


class AmendmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    amendment_no: str
    signed_date: date | None
    type: AmendmentType
    description: str | None
    new_value: Number | None
    new_end_date: date | None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    contract_no: str
    signed_date: date | None
    effective_date: date | None
    duration_days: int | None
    planned_end_date: date | None
    extended_end_date: date | None
    end_date_override: bool
    contract_type: ContractType | None
    price_adjustment: bool
    value: Number | None
    advance_pct: Number | None
    advance_amount: Number | None
    advance_recovery_note: str | None
    performance_bond_pct: Number | None
    performance_bond_amount: Number | None
    warranty_bond_pct: Number | None
    warranty_bond_amount: Number | None
    penalty_rate_pct: Number | None
    penalty_unit: PenaltyUnit | None
    penalty_cap_pct: Number | None
    payment_terms_text: str | None
    payment_term_days: int | None
    copies_text: str | None
    investor_signer: str | None
    investor_account: str | None
    status: ContractStatus
    data_quality_note: str | None
    updated_at: datetime
    consistency: list[IssueOut] = []
    needs_review: bool = False
    parties: list[PartyOut] = []
