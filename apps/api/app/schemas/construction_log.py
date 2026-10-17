"""Request and response bodies of the construction log (`/delivery/logs`)."""

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

EntryState = Literal["not_started", "in_progress", "done", "blocked"]

Text = Annotated[str, Field(max_length=20000)]
Name = Annotated[str, Field(max_length=300)]
Names = list[Name]


class EntryIn(BaseModel):
    entry_date: date
    phase_code: str = Field(min_length=1, max_length=10)
    task_code: str | None = Field(default=None, max_length=20)
    content: str = Field(min_length=1, max_length=20000)
    personnel: Names = Field(default_factory=list, max_length=20)
    note: Text | None = None
    state: EntryState | None = None
    delay_days: int | None = Field(default=None, ge=0, le=3650)


class CarryoverIn(BaseModel):
    phase_code: str = Field(min_length=1, max_length=10)
    task_code: str | None = Field(default=None, max_length=20)
    title: str = Field(min_length=1, max_length=20000)
    result_to_date: Text | None = None
    next_week: Text | None = None
    note: Text | None = None


class MemberWorkIn(BaseModel):
    member_name: str = Field(min_length=1, max_length=200)
    item: str = Field(min_length=1, max_length=20000)
    plan_ref: Text | None = None
    personnel: Names = Field(default_factory=list, max_length=20)
    result: Text | None = None
    next_plan: Text | None = None
    issues_actions: Text | None = None


class LogIn(BaseModel):
    report_date: date | None = None
    recipients: Text | None = None
    reporter_org: str | None = Field(default=None, max_length=200)
    contract_ref: Text | None = None
    coordinator: str | None = Field(default=None, max_length=200)
    environment_note: Text | None = None
    overall_status: Text | None = None
    key_results: Text | None = None
    issues: Text | None = None
    coordination_requests: Text | None = None
    related_report: Text | None = None
    entries: list[EntryIn] = Field(default_factory=list, max_length=300)
    carryovers: list[CarryoverIn] = Field(default_factory=list, max_length=200)
    member_work: list[MemberWorkIn] = Field(default_factory=list, max_length=200)
    # the `updated_at` the editor loaded; a different value means someone saved in between
    expected_updated_at: datetime | None = None


class EntryOut(EntryIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class CarryoverOut(CarryoverIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class MemberWorkOut(MemberWorkIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class LogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    week_start: date
    week_end: date
    report_date: date | None
    recipients: str | None
    reporter_org: str | None
    contract_ref: str | None
    coordinator: str | None
    environment_note: str | None
    overall_status: str | None
    key_results: str | None
    issues: str | None
    coordination_requests: str | None
    related_report: str | None
    entries: list[EntryOut]
    carryovers: list[CarryoverOut]
    member_work: list[MemberWorkOut]
    updated_at: datetime


class LogWeekOut(BaseModel):
    no: int
    week_start: date
    week_end: date
    has_log: bool
    has_report: bool
    report_date: date | None = None
    entry_count: int = 0
    max_delay_days: int = 0


class HistoryOut(BaseModel):
    week_start: date
    entry_date: date
    content: str
    note: str | None
    state: EntryState | None
    delay_days: int | None
    personnel: Names
