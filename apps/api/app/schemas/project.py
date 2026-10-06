import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import Money, Number, Percent

PackageType = Literal["goods", "consulting"]
PackageStatus = Literal[
    "planning",
    "bidding",
    "negotiating",
    "contract_signed",
    "executing",
    "accepted",
    "settled",
    "cancelled",
]
StageCode = Literal[
    "S1_START", "S2_SELECTION", "S3_EXECUTION", "S4_ACCEPTANCE", "S5_PAYMENT_SETTLEMENT"
]
SelectionForm = Literal["open_tender", "direct_appointment_short"]
SelectionMethod = Literal["one_stage_one_envelope", "one_stage_two_envelope", "short_procedure"]
Health = Literal["green", "amber", "red", "grey"]


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    investor_org_id: uuid.UUID | None
    investor_name: str | None = None
    decision_maker: str | None
    total_investment: Number | None
    funding_source: str | None
    start_year: int | None
    end_year: int | None
    location: str | None
    treasury_account: str | None
    project_code_kbnn: str | None
    description: str | None
    package_count: int = 0


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    decision_maker: str | None = None
    total_investment: Money | None = None
    funding_source: str | None = None
    start_year: int | None = Field(default=None, ge=2000, le=2100)
    end_year: int | None = Field(default=None, ge=2000, le=2100)
    location: str | None = None
    treasury_account: str | None = Field(default=None, max_length=50)
    description: str | None = None


class PackageUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    scope_summary: str | None = None
    package_type: PackageType | None = None
    package_price: Money | None = None
    selection_form: SelectionForm | None = None
    selection_method: SelectionMethod | None = None
    approved_duration_days: int | None = Field(default=None, ge=1, le=3650)
    etbmt_no: str | None = Field(default=None, max_length=50)
    kh_lcnt_decision: str | None = None
    approval_decision: str | None = None
    winning_price: Money | None = None
    winning_org_text: str | None = None
    current_stage: StageCode | None = None
    status: PackageStatus | None = None
    notes: str | None = None


class PackageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    number: int
    name: str
    scope_summary: str | None
    package_type: PackageType
    package_price: Number | None
    selection_form: SelectionForm | None
    selection_method: SelectionMethod | None
    approved_duration_days: int | None
    etbmt_no: str | None
    kh_lcnt_decision: str | None
    approval_decision: str | None
    winning_price: Number | None
    winning_org_text: str | None
    current_stage: StageCode
    status: PackageStatus
    progress_pct: Percent
    health: Health
    health_reason: str | None
    is_sensitive: bool
    notes: str | None
    updated_at: datetime


class PackageListItem(PackageOut):
    """Package row plus the figures the list card needs from its contract."""

    contract_no: str | None = None
    contract_value: Number | None = None
    contract_end_date: str | None = None
    needs_review: bool = False
    checklist_pct: float | None = None
