import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

RiskCategory = Literal[
    "schedule", "cost", "quality", "legal", "contract", "supply", "safety", "other"
]
RiskStatus = Literal["open", "mitigating", "occurred", "closed"]
RiskSource = Literal["de_cuong", "analysis", "manual"]
IssueType = Literal["operational", "contract", "schedule", "investor_request", "other"]
IssueStatus = Literal["open", "in_progress", "escalated", "resolved", "closed"]
EditableIssueStatus = Literal["open", "in_progress", "closed"]  # resolve/escalate have endpoints
MeetingType = Literal["kickoff", "package_kickoff", "weekly", "issue_resolution", "other"]
ActionStatus = Literal["open", "done", "cancelled"]
ChangeType = Literal["model", "origin", "allocation", "schedule", "other"]
ChangeStatus = Literal["proposed", "reviewing", "approved", "rejected", "appendix_signed"]
Score = Annotated[int, Field(ge=1, le=5)]


# --- risks ------------------------------------------------------------------------------------


class RiskUpdate(BaseModel):
    package_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    category: RiskCategory | None = None
    probability: Score | None = None
    impact: Score | None = None
    owner_id: uuid.UUID | None = None
    mitigation: str | None = None
    contingency: str | None = None
    group_name: str | None = Field(default=None, max_length=100)
    owner_text: str | None = Field(default=None, max_length=200)
    note: str | None = None
    status: RiskStatus | None = None
    due_date: date | None = None


class RiskIn(RiskUpdate):
    title: str = Field(min_length=1, max_length=500)
    category: RiskCategory
    probability: Score
    impact: Score
    source: RiskSource = "manual"


class RiskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    project_id: uuid.UUID
    package_id: uuid.UUID | None
    title: str
    description: str | None
    category: RiskCategory
    probability: int
    impact: int
    score: int
    level: Literal["low", "medium", "high"] = "low"
    owner_id: uuid.UUID | None
    mitigation: str | None
    contingency: str | None
    group_name: str | None = None
    owner_text: str | None = None
    note: str | None = None
    status: RiskStatus
    due_date: date | None
    source: RiskSource
    last_reviewed_at: datetime | None
    needs_review: bool = False


class MatrixCell(BaseModel):
    probability: int
    impact: int
    count: int
    risk_ids: list[uuid.UUID]


class MatrixOut(BaseModel):
    cells: list[MatrixCell]
    total: int


# --- issues -----------------------------------------------------------------------------------


class IssueIn(BaseModel):
    package_id: uuid.UUID | None = None
    issue_type: IssueType
    level: Annotated[int, Field(ge=1, le=3)] = 1
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    assigned_to: uuid.UUID | None = None
    # Only used for level 3 (entered by hand, SPEC 7.4); ignored otherwise.
    due_at: datetime | None = None


class IssueUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    issue_type: IssueType | None = None
    assigned_to: uuid.UUID | None = None
    status: EditableIssueStatus | None = None
    due_at: datetime | None = None
    # Mandatory whenever the deadline is edited by hand (SPEC 7.4).
    due_reason: str | None = Field(default=None, min_length=3, max_length=500)
    decided_by: str | None = None
    decision_doc_id: uuid.UUID | None = None


class EscalateIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None  # level 3 only


class ResolveIn(BaseModel):
    resolution: str = Field(min_length=1)
    decided_by: str | None = Field(default=None, max_length=300)
    decision_doc_id: uuid.UUID | None = None


class IssueEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ts: datetime
    user_id: uuid.UUID | None
    event: str
    from_level: int | None
    to_level: int | None
    note: str | None


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    package_id: uuid.UUID | None
    issue_type: IssueType
    level: int
    title: str
    description: str | None
    reported_by: uuid.UUID
    assigned_to: uuid.UUID | None
    reported_at: datetime
    escalated_at: datetime | None
    due_at: datetime | None
    status: IssueStatus
    resolution: str | None
    decided_by: str | None
    decision_doc_id: uuid.UUID | None
    resolved_at: datetime | None
    overdue: bool = False
    overdue_days: int = 0


class IssueDetail(IssueOut):
    events: list[IssueEventOut] = []


class HolidayIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=200)


class HolidayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    day: date
    name: str


# --- meetings and change requests -------------------------------------------------------------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Attendee(BaseModel):
    name: Name
    organization: str | None = Field(default=None, max_length=200)


class MeetingUpdate(BaseModel):
    package_id: uuid.UUID | None = None
    meeting_type: MeetingType | None = None
    meeting_date: date | None = None
    location: str | None = Field(default=None, max_length=300)
    chair: str | None = Field(default=None, max_length=200)
    attendees: list[Attendee] | None = Field(default=None, max_length=200)
    minutes: str | None = None
    document_id: uuid.UUID | None = None


class MeetingIn(MeetingUpdate):
    meeting_type: MeetingType
    meeting_date: date


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    package_id: uuid.UUID | None
    meeting_type: MeetingType
    meeting_date: date
    location: str | None
    chair: str | None
    attendees: list[Attendee]
    minutes: str | None
    document_id: uuid.UUID | None
    open_actions: int = 0


class ActionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    package_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    due_date: date | None = None
    status: ActionStatus | None = None


class ActionIn(ActionUpdate):
    title: str = Field(min_length=1, max_length=500)


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meeting_id: uuid.UUID | None
    package_id: uuid.UUID | None
    title: str
    owner_id: uuid.UUID | None
    due_date: date | None
    status: ActionStatus
    overdue: bool = False


class ChangeUpdate(BaseModel):
    change_type: ChangeType | None = None
    description: str | None = Field(default=None, min_length=1)
    proposed_by_org_id: uuid.UUID | None = None
    supervisor_opinion: str | None = None
    tvqlda_opinion: str | None = None
    status: Literal["proposed", "reviewing", "appendix_signed"] | None = (
        None  # decide() does the rest
    )
    document_id: uuid.UUID | None = None
    amendment_id: uuid.UUID | None = None


class ChangeIn(ChangeUpdate):
    package_id: uuid.UUID
    change_type: ChangeType
    description: str = Field(min_length=1)


class DecideIn(BaseModel):
    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class ChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    package_id: uuid.UUID
    change_type: ChangeType
    description: str
    proposed_by_org_id: uuid.UUID | None
    supervisor_opinion: str | None
    tvqlda_opinion: str | None
    status: ChangeStatus
    decided_at: datetime | None
    decided_by: uuid.UUID | None
    decision_note: str | None
    document_id: uuid.UUID | None
    amendment_id: uuid.UUID | None
