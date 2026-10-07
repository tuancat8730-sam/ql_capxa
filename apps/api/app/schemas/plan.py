import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

StepStatus = Literal["not_started", "in_progress", "done", "blocked"]
EffectiveStatus = Literal["not_started", "in_progress", "done", "blocked", "delayed"]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class PlanItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    line_no: int
    name: str
    details: str | None
    unit: str | None
    quantity: int | None
    assignments: list[dict[str, Any]]
    note: str | None


class PlanStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_no: int | None
    group_title: str | None
    step_no: int
    content: str
    time_text: str | None
    start_date: date | None
    end_date: date | None
    estimated: bool
    time_note: str | None
    participants: list[str]
    status: StepStatus
    effective_status: EffectiveStatus = "not_started"
    days_late: int | None = None
    actual_start: date | None
    actual_end: date | None
    tracking_note: str | None


class FindingOut(BaseModel):
    code: str
    severity: Literal["warning", "info"]
    message: str


class ProgressOut(BaseModel):
    done: int
    total: int
    pct: float


class PlanOut(BaseModel):
    id: uuid.UUID
    package_id: uuid.UUID
    addressee: str | None
    legal_basis: str | None
    contract_text: str | None
    contract_start: date | None
    contract_end: date | None
    implement_text: str | None
    implement_start: date | None
    implement_end: date | None
    locations: list[dict[str, Any]]
    signer: str | None
    declared_total: int | None
    total_quantity: int
    source_file_name: str | None
    imported_at: datetime | None
    items: list[PlanItemOut]
    steps: list[PlanStepOut]
    progress: ProgressOut
    findings: list[FindingOut]


class PreviewItem(BaseModel):
    line_no: int
    name: str
    quantity: int | None
    assignments: list[dict[str, Any]]


class PreviewStep(BaseModel):
    step_no: int
    group_no: int | None
    group_title: str | None
    summary: str
    start_date: date | None
    end_date: date | None
    estimated: bool
    keeps_tracking: bool = False


class ImportPreview(BaseModel):
    dry_run: bool
    replaces_existing: bool
    addressee: str | None
    contract_start: date | None
    contract_end: date | None
    implement_start: date | None
    implement_end: date | None
    locations: int
    total_quantity: int
    items: list[PreviewItem]
    steps: list[PreviewStep]
    kept_tracking: int
    findings: list[FindingOut]
    plan_id: uuid.UUID | None = None


class StepUpdate(BaseModel):
    status: StepStatus | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    tracking_note: Note | None = Field(default=None)
