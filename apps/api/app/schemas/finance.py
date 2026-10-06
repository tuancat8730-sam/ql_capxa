import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import Money, Number

PositiveMoney = Annotated[Money, Field(gt=0)]

GuaranteeType = Literal["bid", "performance", "advance", "warranty"]
# `expiring` / `expired` are never stored: they are derived from expiry_date (SPEC 7.2).
StoredGuaranteeStatus = Literal["pending", "valid", "released", "missing"]
EffectiveGuaranteeStatus = Literal["pending", "valid", "expiring", "expired", "released", "missing"]
PaymentType = Literal["advance", "payment", "recovery", "penalty"]
PaymentStatus = Literal["planned", "requested", "approved", "paid", "rejected"]


class FindingOut(BaseModel):
    code: str
    severity: Literal["warning", "critical"]
    message: str
    guarantee_id: str | None = None
    due_date: date | None = None


class GuaranteeUpdate(BaseModel):
    provider_org_id: uuid.UUID | None = None
    guarantee_type: GuaranteeType | None = None
    bank_name: str | None = Field(default=None, max_length=200)
    guarantee_no: str | None = Field(default=None, max_length=100)
    amount: Money | None = None
    issue_date: date | None = None
    effective_from: date | None = None
    expiry_date: date | None = None
    validity_text: str | None = None
    status: StoredGuaranteeStatus | None = None
    required: bool | None = None
    verified: bool | None = None
    verify_note: str | None = None


class GuaranteeIn(GuaranteeUpdate):
    guarantee_type: GuaranteeType


class GuaranteeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    provider_org_id: uuid.UUID | None
    guarantee_type: GuaranteeType
    bank_name: str | None
    guarantee_no: str | None
    amount: Number | None
    issue_date: date | None
    effective_from: date | None
    expiry_date: date | None
    validity_text: str | None
    status: str
    required: bool
    verified: bool
    verify_note: str | None
    effective_status: EffectiveGuaranteeStatus = "valid"
    days_left: int | None = None
    findings: list[FindingOut] = []


class GuaranteeRow(GuaranteeOut):
    contract_no: str
    package_id: uuid.UUID
    package_number: int
    package_name: str


class PaymentUpdate(BaseModel):
    organization_id: uuid.UUID | None = None
    seq: int | None = Field(default=None, ge=0, le=999)
    amount: PositiveMoney | None = None
    requested_date: date | None = None
    due_date: date | None = None
    status: PaymentStatus | None = None
    invoice_no: str | None = Field(default=None, max_length=100)
    treasury_ref: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class PaymentIn(PaymentUpdate):
    payment_type: PaymentType
    amount: PositiveMoney


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    contract_id: uuid.UUID
    organization_id: uuid.UUID | None
    payment_type: PaymentType
    seq: int
    amount: Number
    requested_date: date | None
    due_date: date | None
    paid_date: date | None
    status: PaymentStatus
    invoice_no: str | None
    treasury_ref: str | None
    notes: str | None
    updated_at: datetime


class PaymentRow(PaymentOut):
    contract_no: str
    package_id: uuid.UUID
    package_number: int
    package_name: str


class MarkPaid(BaseModel):
    paid_date: date | None = None
    treasury_ref: str | None = Field(default=None, max_length=100)


class DisbursementItem(BaseModel):
    package_id: uuid.UUID | None = None
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)
    planned_amount: Money
    actual_amount: Money | None = None


class DisbursementPlanIn(BaseModel):
    items: list[DisbursementItem] = Field(max_length=600)


class DisbursementPlanOut(BaseModel):
    items: list[DisbursementItem]
    planned_total: Number
    actual_total: Number
