import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

TaskStatus = Literal["not_started", "in_progress", "done", "on_hold"]
TaskState = Literal["done", "paused", "late", "stale", "todo", "behind", "progress"]
ReportStatus = Literal["received", "needs_more"]
WeekState = Literal["received", "needs_more", "missing", "current", "future"]
DecisionStatus = Literal["pending", "decided", "not_applicable"]
Chip = Literal["good", "warn", "bad", "accent", "stale", "muted"]
Pct = Annotated[int, Field(ge=0, le=100)]


def _http_link(value: str | None) -> str | None:
    if value and not value.lower().startswith(("http://", "https://")):
        raise ValueError("link phải bắt đầu bằng http:// hoặc https://")
    return value


Link = Annotated[str | None, AfterValidator(_http_link), Field(max_length=2000)]


# --- schedule ---------------------------------------------------------------------------------


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    phase_code: str
    phase_name: str
    name: str
    is_milestone: bool
    plan_start: date
    plan_end: date
    plan_days: int
    tracked: bool
    status: TaskStatus
    pct: int
    actual_start: date | None
    actual_end: date | None
    note: str | None
    updated_at: datetime
    state: TaskState = "todo"
    late_days: int = 0


class TaskUpdate(BaseModel):
    status: TaskStatus | None = None
    pct: Pct | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    note: str | None = Field(default=None, max_length=4000)


# --- weekly reports ---------------------------------------------------------------------------


class ReportIn(BaseModel):
    report_no: str | None = Field(default=None, max_length=50)
    status: ReportStatus = "received"
    submitted_on: date | None = None
    link: Link = None
    planned_pct: Pct | None = None
    actual_pct: Pct | None = None
    done: str | None = None
    issues: str | None = None
    recommendations: str | None = None
    next_plan: str | None = None
    risk_ids: list[uuid.UUID] = Field(default_factory=list)


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    week_start: date
    report_no: str | None
    status: ReportStatus
    submitted_on: date | None
    link: str | None
    planned_pct: int | None
    actual_pct: int | None
    done: str | None
    issues: str | None
    recommendations: str | None
    next_plan: str | None
    risk_ids: list[uuid.UUID]
    updated_at: datetime


class WeekOut(BaseModel):
    no: int
    start: date
    end: date
    state: WeekState
    report: ReportOut | None = None
    # the plan's progress at the end of the period: what the form suggests for "planned"
    suggested_planned_pct: int
    # progress worked out from the tasks right now, for "actual" on the current period
    suggested_actual_pct: int


# --- open decisions ---------------------------------------------------------------------------


class DecisionIn(BaseModel):
    title: str = Field(min_length=1, max_length=2000)
    reason: str | None = None
    status: DecisionStatus = "pending"
    due_date: date | None = None
    decision: str | None = None
    decided_on: date | None = None
    no: int | None = Field(default=None, ge=1)


class DecisionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=2000)
    reason: str | None = None
    status: DecisionStatus | None = None
    due_date: date | None = None
    decision: str | None = None
    decided_on: date | None = None
    no: int | None = Field(default=None, ge=1)


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    no: int
    title: str
    reason: str | None
    status: DecisionStatus
    due_date: date | None
    decision: str | None
    decided_on: date | None
    updated_at: datetime
    overdue: bool = False


# --- overview ---------------------------------------------------------------------------------


class AttentionItem(BaseModel):
    rank: int
    chip: Chip
    label: str
    title: str
    sub: str
    target: Literal["task", "week", "risks"]
    ref: str


class MilestoneNext(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    date: date
    days_left: int


class PhaseSummary(BaseModel):
    code: str
    name: str
    start: date
    end: date
    actual_pct: float
    plan_pct: float
    state: TaskState


class CurvePoint(BaseModel):
    date: date
    pct: float


class OverviewOut(BaseModel):
    today: date
    project_start: date | None
    project_end: date | None
    has_progress: bool
    actual_pct: float
    plan_pct: float
    diff: int
    next_milestone: MilestoneNext | None
    late_count: int
    stale_count: int
    weeks_ended: int
    weeks_received: int
    pending_decisions: int
    attention: list[AttentionItem]
    phases: list[PhaseSummary]
    plan_curve: list[CurvePoint]
    report_points: list[CurvePoint]
