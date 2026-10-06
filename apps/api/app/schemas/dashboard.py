import uuid
from datetime import date

from pydantic import BaseModel

from app.schemas.alert import AlertCounts, AlertOut
from app.schemas.project import Health, StageCode
from app.schemas.risk import MatrixOut, RiskOut
from app.schemas.types import Number


class DashProject(BaseModel):
    name: str
    code: str
    investor_name: str | None
    total_investment: Number | None
    funding_source: str | None
    start_year: int | None
    end_year: int | None
    package_count: int
    # Package 06 (the TVQLDA contract): countdown to its planned end (SPEC 4.2 #1)
    tvqlda_end_date: date | None
    tvqlda_days_left: int | None


class DashPackage(BaseModel):
    id: uuid.UUID
    number: int
    name: str
    package_type: str
    status: str
    contractor: str | None
    winning_price: Number | None
    package_price: Number | None
    current_stage: StageCode
    progress_pct: Number
    health: Health
    health_reason: str | None


class DashFinance(BaseModel):
    total_package_price: Number
    total_winning_price: Number
    total_contract_value: Number
    total_advance: Number
    total_paid: Number
    planned_total: Number
    planned_to_date: Number
    # paid / planned to date, in %; None while no plan exists (SPEC 4.2 #3)
    disbursement_rate_pct: Number | None


class Milestone(BaseModel):
    date: date
    days_left: int
    kind: str  # contract_end | guarantee_expiry | stage_end | issue_due | action_due | payment_due
    title: str
    package_id: uuid.UUID | None
    package_number: int | None
    entity_type: str
    entity_id: str


class SummaryOut(BaseModel):
    today: date
    project: DashProject
    packages: list[DashPackage]
    finance: DashFinance
    milestones: list[Milestone]


class CashflowMonth(BaseModel):
    year: int
    month: int
    planned: Number
    actual: Number


class CashflowOut(BaseModel):
    months: list[CashflowMonth]


class TopRisksOut(BaseModel):
    items: list[RiskOut]
    matrix: MatrixOut


class DashAlertsOut(BaseModel):
    counts: AlertCounts
    items: list[AlertOut]


class MissingDocsPackage(BaseModel):
    package_id: uuid.UUID
    number: int
    name: str
    required: int
    missing: int


class MissingDocsOut(BaseModel):
    total_missing: int
    packages: list[MissingDocsPackage]
