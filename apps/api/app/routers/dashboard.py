"""Dashboard blocks (SPEC 4.2): each block has its own endpoint so the page loads them apart.

`/dashboard/timeline` (block 8) lives in the progress router next to the Gantt data.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import ColumnElement, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.core.deps import SessionDep, require
from app.core.rbac import Level
from app.models import (
    ActionItem,
    Alert,
    ChecklistItem,
    Contract,
    DisbursementPlan,
    Guarantee,
    Issue,
    Organization,
    Package,
    PackagePlan,
    Payment,
    PlanStep,
    Risk,
    StagePlan,
    User,
)
from app.routers.project import get_single_project
from app.schemas.alert import AlertCounts, AlertOut
from app.schemas.dashboard import (
    CashflowMonth,
    CashflowOut,
    DashAlertsOut,
    DashFinance,
    DashPackage,
    DashProject,
    Milestone,
    MissingDocsOut,
    MissingDocsPackage,
    SummaryOut,
    TopRisksOut,
)
from app.schemas.risk import MatrixCell, MatrixOut, RiskOut
from app.services.alert_rules import report_due
from app.services.finance import today_local
from app.services.risk_rules import matrix_counts, risk_level, risk_needs_review

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

Reader = Annotated[User, Depends(require("package", Level.READ))]

MILESTONE_DAYS = 30
TOP_ALERTS = 10
TOP_RISKS = 5
_PAID_KINDS = ("advance", "payment")
_CLOSED_PACKAGE = ("settled", "cancelled")


async def _packages(session: AsyncSession) -> list[Package]:
    rows = await session.execute(
        select(Package).where(Package.deleted_at.is_(None)).order_by(Package.number)
    )
    return list(rows.scalars().all())


async def _sum(
    session: AsyncSession,
    column: InstrumentedAttribute[Decimal | None],
    *where: ColumnElement[bool],
) -> Decimal:
    stmt = select(func.coalesce(func.sum(column), 0)).where(*where)
    return Decimal(str((await session.execute(stmt)).scalar_one()))


async def _finance(session: AsyncSession, today: date) -> DashFinance:
    live_pkg = Package.deleted_at.is_(None)
    live_contract = Contract.deleted_at.is_(None)
    plan_rows = list((await session.execute(select(DisbursementPlan))).scalars().all())
    planned_total = sum((r.planned_amount for r in plan_rows), Decimal(0))
    planned_to_date = sum(
        (r.planned_amount for r in plan_rows if (r.year, r.month) <= (today.year, today.month)),
        Decimal(0),
    )
    paid = await _sum(
        session, Payment.amount, Payment.status == "paid", Payment.payment_type.in_(_PAID_KINDS)
    )
    rate = (paid / planned_to_date * 100).quantize(Decimal("0.01")) if planned_to_date else None
    return DashFinance(
        total_package_price=await _sum(session, Package.package_price, live_pkg),
        total_winning_price=await _sum(session, Package.winning_price, live_pkg),
        total_contract_value=await _sum(session, Contract.value, live_contract),
        total_advance=await _sum(session, Contract.advance_amount, live_contract),
        total_paid=paid,
        planned_total=planned_total,
        planned_to_date=planned_to_date,
        disbursement_rate_pct=rate,
    )


async def _milestones(session: AsyncSession, today: date) -> list[Milestone]:
    last = today + timedelta(days=MILESTONE_DAYS)
    numbers = {p.id: p.number for p in await _packages(session)}
    out: list[Milestone] = []

    def add(
        day: date | None,
        kind: str,
        title: str,
        package_id: uuid.UUID | None,
        entity_type: str,
        entity_id: object,
    ) -> None:
        if day is None or not (today <= day <= last):
            return
        out.append(
            Milestone(
                date=day,
                days_left=(day - today).days,
                kind=kind,
                title=title,
                package_id=package_id,
                package_number=numbers.get(package_id) if package_id else None,
                entity_type=entity_type,
                entity_id=str(entity_id),
            )
        )

    contracts = await session.execute(
        select(Contract, Package)
        .join(Package, Package.id == Contract.package_id)
        .where(Contract.deleted_at.is_(None), Package.status.notin_(_CLOSED_PACKAGE))
    )
    for contract, package in contracts.all():
        end = contract.extended_end_date or contract.planned_end_date
        title = f"Hết hạn hợp đồng {contract.contract_no}"
        add(end, "contract_end", title, package.id, "contract", contract.id)

    guarantees = await session.execute(
        select(Guarantee, Contract.package_id)
        .join(Contract, Contract.id == Guarantee.contract_id)
        .where(Guarantee.status.notin_(("released", "missing")), Guarantee.expiry_date.is_not(None))
    )
    for g, package_id in guarantees.all():
        title = f"Hết hạn bảo lãnh {g.guarantee_type}"
        add(g.expiry_date, "guarantee_expiry", title, package_id, "guarantee", g.id)

    stages = await session.execute(
        select(StagePlan).where(StagePlan.status != "done", StagePlan.planned_end.is_not(None))
    )
    for s in stages.scalars():
        title = f"Hạn giai đoạn {s.name}"
        add(s.planned_end, "stage_end", title, s.package_id, "stage_plan", s.id)

    issues = await session.execute(
        select(Issue).where(Issue.status.notin_(("resolved", "closed")), Issue.due_at.is_not(None))
    )
    for issue in issues.scalars():
        if issue.due_at is not None:
            title = f"Hạn vướng mắc {issue.code}"
            add(issue.due_at.date(), "issue_due", title, issue.package_id, "issue", issue.id)

    actions = await session.execute(
        select(ActionItem).where(ActionItem.status == "open", ActionItem.due_date.is_not(None))
    )
    for a in actions.scalars():
        title = f"Hạn đầu việc: {a.title}"
        add(a.due_date, "action_due", title, a.package_id, "action_item", a.id)

    payments = await session.execute(
        select(Payment, Contract.package_id)
        .join(Contract, Contract.id == Payment.contract_id)
        .where(Payment.status.in_(("planned", "requested")), Payment.due_date.is_not(None))
    )
    for p, package_id in payments.all():
        add(p.due_date, "payment_due", "Hạn đợt thanh toán", package_id, "payment", p.id)

    plan_steps = await session.execute(
        select(PlanStep, PackagePlan.package_id)
        .join(PackagePlan, PackagePlan.id == PlanStep.plan_id)
        .where(PlanStep.status != "done", PlanStep.end_date.is_not(None))
    )
    for ps, package_id in plan_steps.all():
        first = ps.content.strip().splitlines()[0].lstrip("-– ").strip()[:80]
        title = f"Bước {ps.step_no} kế hoạch: {first}"
        add(ps.end_date, "plan_step", title, package_id, "plan_step", ps.id)

    for offset in range(MILESTONE_DAYS + 1):
        day = today + timedelta(days=offset)
        for report in report_due(day):
            add(day, "report_due", report.title, None, "report", report.level)

    return sorted(out, key=lambda m: (m.date, m.kind, m.title))


@router.get("/summary", response_model=SummaryOut)
async def summary(_: Reader, session: SessionDep) -> SummaryOut:
    """Project card, the strip of packages, finance figures and the next 30 days (4.2 #1-4)."""
    today = today_local()
    project = await get_single_project(session)
    investor = (
        await session.get(Organization, project.investor_org_id)
        if project.investor_org_id
        else None
    )
    packages = await _packages(session)

    tvqlda_end: date | None = None
    for package in packages:
        if package.consulting_role == "tvqlda":
            contract = (
                (
                    await session.execute(
                        select(Contract).where(
                            Contract.package_id == package.id, Contract.deleted_at.is_(None)
                        )
                    )
                )
                .scalars()
                .first()
            )
            if contract is not None:
                tvqlda_end = contract.extended_end_date or contract.planned_end_date
            break

    return SummaryOut(
        today=today,
        project=DashProject(
            name=project.name,
            code=project.code,
            investor_name=investor.name if investor else None,
            total_investment=project.total_investment,
            funding_source=project.funding_source,
            start_year=project.start_year,
            end_year=project.end_year,
            package_count=len(packages),
            tvqlda_end_date=tvqlda_end,
            tvqlda_days_left=(tvqlda_end - today).days if tvqlda_end else None,
        ),
        packages=[
            DashPackage(
                id=p.id,
                number=p.number,
                name=p.name,
                package_type=p.package_type,
                status=p.status,
                contractor=p.winning_org_text,
                winning_price=p.winning_price,
                package_price=p.package_price,
                current_stage=p.current_stage,
                progress_pct=p.progress_pct,
                health=p.health,
                health_reason=p.health_reason,
            )
            for p in packages
        ],
        finance=await _finance(session, today),
        milestones=await _milestones(session, today),
    )


@router.get("/cashflow", response_model=CashflowOut)
async def cashflow(_: Reader, session: SessionDep) -> CashflowOut:
    """Planned vs actual disbursement per month (4.2 #3).

    Actual comes from payments marked paid; a month without any paid payment falls back to the
    `actual_amount` typed into the plan.
    """
    planned: dict[tuple[int, int], Decimal] = {}
    typed_actual: dict[tuple[int, int], Decimal] = {}
    for row in (await session.execute(select(DisbursementPlan))).scalars():
        key = (row.year, row.month)
        planned[key] = planned.get(key, Decimal(0)) + row.planned_amount
        if row.actual_amount is not None:
            typed_actual[key] = typed_actual.get(key, Decimal(0)) + row.actual_amount

    paid: dict[tuple[int, int], Decimal] = {}
    payments = await session.execute(
        select(Payment.paid_date, Payment.amount).where(
            Payment.status == "paid",
            Payment.payment_type.in_(_PAID_KINDS),
            Payment.paid_date.is_not(None),
        )
    )
    for paid_date, amount in payments.all():
        if paid_date is None:
            continue
        key = (paid_date.year, paid_date.month)
        paid[key] = paid.get(key, Decimal(0)) + amount

    months = sorted(set(planned) | set(typed_actual) | set(paid))
    return CashflowOut(
        months=[
            CashflowMonth(
                year=y,
                month=m,
                planned=planned.get((y, m), Decimal(0)),
                actual=paid.get((y, m), typed_actual.get((y, m), Decimal(0))),
            )
            for y, m in months
        ]
    )


@router.get("/top-risks", response_model=TopRisksOut)
async def top_risks(_: Reader, session: SessionDep) -> TopRisksOut:
    """Five highest-scoring open risks and the 5x5 heat map (4.2 #6)."""
    now = datetime.now(UTC)
    open_risks = list(
        (await session.execute(select(Risk).where(Risk.status != "closed"))).scalars().all()
    )
    ranked = sorted(open_risks, key=lambda r: (-r.score, r.code))[:TOP_RISKS]
    items = []
    for risk in ranked:
        out = RiskOut.model_validate(risk)
        out.level = risk_level(risk.score)
        out.needs_review = risk_needs_review(
            risk.status, risk.created_at, risk.last_reviewed_at, now
        )
        items.append(out)
    counts = matrix_counts((r.probability, r.impact) for r in open_risks)
    ids: dict[tuple[int, int], list[uuid.UUID]] = {}
    for r in open_risks:
        ids.setdefault((r.probability, r.impact), []).append(r.id)
    cells = [
        MatrixCell(probability=p, impact=i, count=n, risk_ids=ids.get((p, i), []))
        for (p, i), n in sorted(counts.items(), reverse=True)
    ]
    return TopRisksOut(items=items, matrix=MatrixOut(cells=cells, total=len(open_risks)))


@router.get("/alerts", response_model=DashAlertsOut)
async def dashboard_alerts(_: Reader, session: SessionDep) -> DashAlertsOut:
    """Open alerts by severity and the ten most serious ones (4.2 #5)."""
    active = Alert.status.in_(("open", "acknowledged"))
    grouped = (
        await session.execute(
            select(Alert.severity, func.count()).where(active).group_by(Alert.severity)
        )
    ).all()
    counts = AlertCounts(**{sev: n for sev, n in grouped})
    counts.total = counts.critical + counts.warning + counts.info
    order = case((Alert.severity == "critical", 0), (Alert.severity == "warning", 1), else_=2)
    rows = (
        await session.execute(
            select(Alert, Package.number)
            .outerjoin(Package, Package.id == Alert.package_id)
            .where(active)
            .order_by(order, Alert.due_date.asc().nulls_last(), Alert.first_seen_at.desc())
            .limit(TOP_ALERTS)
        )
    ).all()
    items = []
    for alert, number in rows:
        out = AlertOut.model_validate(alert)
        out.package_number = number
        out.can_snooze = alert.severity != "critical"
        items.append(out)
    return DashAlertsOut(counts=counts, items=items)


@router.get("/documents", response_model=MissingDocsOut)
async def missing_documents(_: Reader, session: SessionDep) -> MissingDocsOut:
    """Required checklist items still missing, per package (4.2 #7)."""
    rows = (
        await session.execute(
            select(
                Package.id,
                Package.number,
                Package.name,
                func.count(ChecklistItem.id).filter(ChecklistItem.status != "not_applicable"),
                func.count(ChecklistItem.id).filter(ChecklistItem.status == "missing"),
            )
            .join(ChecklistItem, ChecklistItem.package_id == Package.id)
            .where(Package.deleted_at.is_(None), ChecklistItem.required.is_(True))
            .group_by(Package.id, Package.number, Package.name)
            .order_by(Package.number)
        )
    ).all()
    packages = [
        MissingDocsPackage(package_id=pid, number=n, name=name, required=req, missing=miss)
        for pid, n, name, req, miss in rows
    ]
    return MissingDocsOut(total_missing=sum(p.missing for p in packages), packages=packages)
