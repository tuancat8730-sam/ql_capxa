import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.types import Number, Percent

StageStatus = Literal["not_started", "in_progress", "done", "delayed", "blocked"]
TaskStatus = Literal["todo", "doing", "done", "blocked"]
TaskPriority = Literal["low", "normal", "high"]
StageCode = Literal[
    "S1_START", "S2_SELECTION", "S3_EXECUTION", "S4_ACCEPTANCE", "S5_PAYMENT_SETTLEMENT"
]
Weight = Percent  # 0..100, two decimals


class StagePlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    planned_start: date | None = None
    planned_end: date | None = None
    actual_start: date | None = None
    actual_end: date | None = None
    progress_pct: Percent | None = None
    weight: Weight | None = None
    status: Literal["not_started", "in_progress", "done", "blocked"] | None = None
    notes: str | None = None


class StagePlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    stage_code: StageCode
    name: str
    planned_start: date | None
    planned_end: date | None
    actual_start: date | None
    actual_end: date | None
    progress_pct: Number
    weight: Number
    status: StageStatus
    effective_status: StageStatus = "not_started"
    notes: str | None
    task_count: int = 0
    tasks_done: int = 0


class StagesOut(BaseModel):
    package_progress: Number
    current_stage: StageCode
    stages: list[StagePlanOut]


class StageUpdateOut(BaseModel):
    stage: StagePlanOut
    package_progress: Number
    current_stage: StageCode


class TaskUpdate(BaseModel):
    stage_plan_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    assignee_id: uuid.UUID | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    actual_end: date | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    weight: Weight | None = None
    notes: str | None = None
    depends_on: list[uuid.UUID] | None = Field(default=None, max_length=50)


class TaskIn(TaskUpdate):
    title: str = Field(min_length=1, max_length=500)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    stage_plan_id: uuid.UUID | None
    title: str
    assignee_id: uuid.UUID | None
    planned_start: date | None
    planned_end: date | None
    actual_end: date | None
    status: TaskStatus
    priority: TaskPriority
    weight: Number
    notes: str | None
    depends_on: list[uuid.UUID]
    # True when every task of this task's stage is done: the UI then offers to close the stage.
    stage_all_done: bool = False


class ProgressLogUpdate(BaseModel):
    progress_pct: Percent | None = None
    summary: str | None = None
    issues: str | None = None
    next_steps: str | None = None
    workers: int | None = Field(default=None, ge=0, le=100_000)
    weather: str | None = Field(default=None, max_length=100)
    attachments: list[uuid.UUID] | None = Field(default=None, max_length=30)


class ProgressLogIn(ProgressLogUpdate):
    log_date: date
    progress_pct: Percent
    # Same value as the Idempotency-Key header (offline queue's client id).
    client_id: str | None = Field(default=None, min_length=8, max_length=64)


class ProgressLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    package_id: uuid.UUID
    log_date: date
    progress_pct: Number
    summary: str | None
    issues: str | None
    next_steps: str | None
    workers: int | None
    weather: str | None
    author_id: uuid.UUID
    author_name: str | None = None
    attachments: list[uuid.UUID]
    created_at: datetime


class TimelineStage(BaseModel):
    id: uuid.UUID
    stage_code: StageCode
    name: str
    planned_start: date | None
    planned_end: date | None
    actual_start: date | None
    actual_end: date | None
    progress_pct: Number
    effective_status: StageStatus


class TimelineContract(BaseModel):
    contract_no: str
    start: date | None
    end: date | None
    end_date_override: bool
    extended_end_date: date | None


class TimelinePackage(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    health: str
    progress_pct: Number
    stages: list[TimelineStage]
    contract: TimelineContract | None


class TimelineOut(BaseModel):
    today: date
    range_start: date | None
    range_end: date | None
    packages: list[TimelinePackage]
