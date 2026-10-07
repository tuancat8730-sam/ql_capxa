"""Alert engine (SPEC 7.1, 4.10): gathers facts, runs the rules, persists alerts, sets health.

Alerts are de-duplicated by `fingerprint`: a condition that still holds updates its alert in
place, one that no longer holds is closed (`resolved`), one that comes back reopens the alert.
"""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    Alert,
    ChecklistItem,
    Contract,
    Guarantee,
    Holiday,
    Issue,
    Package,
    PackagePlan,
    Payment,
    PlanStep,
    ProgressLog,
    StagePlan,
)
from app.services import alert_rules as rules
from app.services.alert_rules import Candidate
from app.services.finance import guarantee_findings

logger = logging.getLogger("qlda.alerts")

_LIVE = ("open", "acknowledged", "suppressed")
_ACTIVE = ("open", "acknowledged")


@dataclass(frozen=True)
class RunResult:
    created: int = 0
    updated: int = 0
    reopened: int = 0
    resolved: int = 0
    health_changed: int = 0


def package_label(package: Package) -> str:
    return f"Gói {package.number:02d}"


def _contract_end(contract: Contract) -> date | None:
    return contract.extended_end_date or contract.planned_end_date


_GUARANTEE_TITLES = {
    "GUARANTEE_EXPIRING": "bảo lãnh sắp hết hạn",
    "ADVANCE_GUARANTEE_SHORT": "bảo lãnh tạm ứng không đủ thời hạn",
    "GUARANTEE_MISSING": "thiếu bảo lãnh",
}


async def _guarantee_candidates(
    session: AsyncSession, package: Package, contract: Contract, today: date
) -> list[Candidate]:
    guarantees = list(
        (await session.execute(select(Guarantee).where(Guarantee.contract_id == contract.id)))
        .scalars()
        .all()
    )
    known = {str(g.id) for g in guarantees}
    label = package_label(package)
    out: list[Candidate] = []
    for f in await guarantee_findings(session, contract, guarantees, today):
        entity_id = f.guarantee_id or str(contract.id)
        out.append(
            Candidate(
                f.code,
                f.severity,
                "guarantee" if entity_id in known else "contract",
                entity_id,
                f"{label}: {_GUARANTEE_TITLES.get(f.code, 'bảo lãnh')}",
                f.message,
                package_id=str(package.id),
                due_date=f.due_date,
            )
        )
    return out


async def _first_contract(session: AsyncSession, package: Package) -> Contract | None:
    return (
        (
            await session.execute(
                select(Contract)
                .where(Contract.package_id == package.id, Contract.deleted_at.is_(None))
                .order_by(Contract.signed_date.nulls_last())
            )
        )
        .scalars()
        .first()
    )


async def _missing_items(session: AsyncSession, package: Package) -> list[tuple[str, str, str]]:
    rows = (
        (
            await session.execute(
                select(ChecklistItem)
                .where(
                    ChecklistItem.package_id == package.id,
                    ChecklistItem.required.is_(True),
                    ChecklistItem.status == "missing",
                )
                .order_by(ChecklistItem.sort_order)
            )
        )
        .scalars()
        .all()
    )
    return [(str(i.id), i.stage_code, i.title) for i in rows]


async def _payment_candidates(
    session: AsyncSession, package: Package, contract: Contract, today: date
) -> list[Candidate]:
    payments = (
        (
            await session.execute(
                select(Payment).where(
                    Payment.contract_id == contract.id,
                    Payment.payment_type.in_(("advance", "payment")),
                )
            )
        )
        .scalars()
        .all()
    )
    out: list[Candidate] = []
    for p in payments:
        out += rules.payment_due(
            payment_id=str(p.id),
            package_id=str(package.id),
            package_label=package_label(package),
            due_date=p.due_date,
            status=p.status,
            today=today,
        )
    return out


async def _plan_step_candidates(
    session: AsyncSession, package: Package, today: date
) -> list[Candidate]:
    steps = (
        (
            await session.execute(
                select(PlanStep)
                .join(PackagePlan, PackagePlan.id == PlanStep.plan_id)
                .where(PackagePlan.package_id == package.id, PlanStep.status != "done")
            )
        )
        .scalars()
        .all()
    )
    out: list[Candidate] = []
    for step in steps:
        out += rules.plan_step_overdue(
            step_id=str(step.id),
            package_id=str(package.id),
            package_label=package_label(package),
            step_no=step.step_no,
            content=step.content,
            end_date=step.end_date,
            status=step.status,
            today=today,
        )
    return out


async def collect_candidates(
    session: AsyncSession, now: datetime | None = None
) -> tuple[list[Candidate], dict[str, Decimal], set[str]]:
    """Every alert that should exist right now.

    Returns the candidates, the progress gap (points behind plan) per package id and the ids of
    packages that have a contract.
    """
    tz = ZoneInfo(get_settings().app_timezone)
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    now_local = now_utc.astimezone(tz)
    today = now_local.date()

    packages = list(
        (
            await session.execute(
                select(Package).where(Package.deleted_at.is_(None)).order_by(Package.number)
            )
        )
        .scalars()
        .all()
    )
    holidays = frozenset((await session.execute(select(Holiday.day))).scalars().all())
    candidates: list[Candidate] = []
    gaps: dict[str, Decimal] = {}
    with_contract: set[str] = set()
    contract_ends: list[rules.ContractEnd] = []
    acceptance_dates: dict[str, date] = {}

    for package in packages:
        pid = str(package.id)
        label = package_label(package)
        contract = await _first_contract(session, package)
        stages = list(
            (await session.execute(select(StagePlan).where(StagePlan.package_id == package.id)))
            .scalars()
            .all()
        )
        closed = package.status in {"settled", "cancelled"}

        end = _contract_end(contract) if contract is not None else None
        if contract is not None:
            with_contract.add(pid)
        contract_ends.append(
            rules.ContractEnd(
                pid, label, package.package_type, package.consulting_role, end, package.status
            )
        )
        if closed:
            continue

        if contract is not None:
            candidates += rules.contract_ending(
                contract_id=str(contract.id),
                package_id=pid,
                package_label=label,
                end=_contract_end(contract),
                progress_pct=package.progress_pct,
                today=today,
            )
            candidates += await _guarantee_candidates(session, package, contract, today)
            candidates += await _payment_candidates(session, package, contract, today)

        for s in stages:
            candidates += rules.stage_delayed(
                stage_id=str(s.id),
                package_id=pid,
                package_label=label,
                stage_name=s.name,
                status=s.status,
                planned_end=s.planned_end,
                progress_pct=s.progress_pct,
                today=today,
            )
            if s.stage_code == "S4_ACCEPTANCE" and s.planned_end is not None:
                acceptance_dates[pid] = s.planned_end

        planned = rules.planned_progress(
            [
                rules.StageSchedule(s.weight, s.planned_start, s.planned_end, s.status)
                for s in stages
            ],
            today,
        )
        gaps[pid] = rules.progress_gap(package.progress_pct, planned)
        if contract is not None:
            candidates += rules.progress_behind(
                package_id=pid, package_label=label, actual=package.progress_pct, planned=planned
            )

        candidates += await _plan_step_candidates(session, package, today)

        candidates += rules.doc_missing(
            package_id=pid,
            package_label=label,
            package_status=package.status,
            current_stage=package.current_stage,
            missing=await _missing_items(session, package),
        )

        has_log = (
            await session.execute(
                select(ProgressLog.id)
                .where(ProgressLog.package_id == package.id, ProgressLog.log_date == today)
                .limit(1)
            )
        ).first() is not None
        candidates += rules.daily_log_missing(
            package_id=pid,
            package_label=label,
            package_status=package.status,
            has_log_today=has_log,
            now_local=now_local,
            holidays=holidays,
        )

    open_issues = (
        (await session.execute(select(Issue).where(Issue.status.notin_(("resolved", "closed")))))
        .scalars()
        .all()
    )
    for issue in open_issues:
        candidates += rules.issue_sla(
            issue_id=str(issue.id),
            code=issue.code,
            title=issue.title,
            package_id=str(issue.package_id) if issue.package_id else None,
            due_at=issue.due_at,
            status=issue.status,
            now=now_utc,
        )

    candidates += rules.report_due(today)
    candidates += rules.cross_package_dependency(contract_ends, acceptance_dates, today)

    unique: dict[str, Candidate] = {}
    for c in candidates:  # one alert per fingerprint, keeping the most severe
        old = unique.get(c.fingerprint)
        if old is None or rules.SEVERITY_RANK[c.severity] > rules.SEVERITY_RANK[old.severity]:
            unique[c.fingerprint] = c
    return list(unique.values()), gaps, with_contract


def _as_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None


def _snooze_over(alert: Alert, now: datetime) -> bool:
    return alert.snoozed_until is not None and alert.snoozed_until <= now


def _reopen(alert: Alert, *, clear_ack: bool, clear_snooze: bool, reset_notice: bool) -> None:
    alert.status = "open"
    alert.resolved_at = None
    if clear_ack:
        alert.acknowledged_by = None
        alert.acknowledged_at = None
    if clear_snooze:
        alert.snoozed_until = None
        alert.snooze_reason = None
    if reset_notice:
        alert.notified_at = None


async def sync_alerts(
    session: AsyncSession, candidates: list[Candidate], now: datetime
) -> tuple[RunResult, dict[str, Alert]]:
    """Create/update/reopen/resolve alerts so the table matches `candidates`."""
    existing = {a.fingerprint: a for a in (await session.execute(select(Alert))).scalars().all()}
    wanted = {c.fingerprint for c in candidates}
    created = updated = reopened = resolved = 0
    live: dict[str, Alert] = {}

    for c in candidates:
        alert = existing.get(c.fingerprint)
        if alert is None:
            alert = Alert(
                alert_type=c.alert_type,
                severity=c.severity,
                entity_type=c.entity_type,
                entity_id=c.entity_id,
                package_id=_as_uuid(c.package_id),
                title=c.title,
                message=c.message,
                due_date=c.due_date,
                status="open",
                fingerprint=c.fingerprint,
            )
            session.add(alert)
            created += 1
            live[c.fingerprint] = alert
            continue

        escalated = rules.SEVERITY_RANK[c.severity] > rules.SEVERITY_RANK[alert.severity]
        if alert.status == "resolved":
            _reopen(alert, clear_ack=True, clear_snooze=True, reset_notice=True)
            reopened += 1
        elif alert.status == "suppressed" and (
            c.severity == "critical" or _snooze_over(alert, now)
        ):
            # critical alerts cannot be snoozed (SPEC 7.1); an expired snooze simply ends
            _reopen(alert, clear_ack=False, clear_snooze=True, reset_notice=False)
            reopened += 1
        elif alert.status == "acknowledged" and escalated:
            _reopen(alert, clear_ack=True, clear_snooze=False, reset_notice=False)
            reopened += 1
        if escalated and c.severity == "critical":
            alert.notified_at = None

        fresh = (c.severity, c.title, c.message, c.due_date)
        if (alert.severity, alert.title, alert.message, alert.due_date) != fresh:
            alert.severity, alert.title, alert.message, alert.due_date = fresh
            updated += 1
        live[c.fingerprint] = alert

    for fingerprint, alert in existing.items():
        if fingerprint not in wanted and alert.status in _LIVE:
            alert.status = "resolved"
            alert.resolved_at = now
            resolved += 1

    await session.flush()
    return RunResult(created, updated, reopened, resolved), live


async def apply_health(
    session: AsyncSession,
    live: dict[str, Alert],
    gaps: dict[str, Decimal],
    with_contract: set[str],
) -> int:
    """SPEC 7.3: recompute each package's health from its open alerts and progress gap."""
    severities: dict[str, list[str]] = defaultdict(list)
    for alert in live.values():
        if alert.status in _ACTIVE and alert.package_id is not None:
            severities[str(alert.package_id)].append(alert.severity)
    changed = 0
    result = await session.execute(select(Package).where(Package.deleted_at.is_(None)))
    for package in result.scalars():
        pid = str(package.id)
        health = rules.package_health(
            status=package.status,
            has_contract=pid in with_contract,
            open_severities=severities.get(pid, []),
            gap=gaps.get(pid, Decimal(0)),
        )
        if (package.health, package.health_reason) != (health.value, health.reason):
            package.health = health.value
            package.health_reason = health.reason
            changed += 1
    await session.flush()
    return changed


async def run_alerts(session: AsyncSession, now: datetime | None = None) -> RunResult:
    """One full pass: evaluate every rule, sync alerts, refresh package health, commit."""
    now_utc = (now or datetime.now(UTC)).astimezone(UTC)
    candidates, gaps, with_contract = await collect_candidates(session, now_utc)
    result, live = await sync_alerts(session, candidates, now_utc)
    health_changed = await apply_health(session, live, gaps, with_contract)
    await session.commit()
    final = RunResult(
        result.created, result.updated, result.reopened, result.resolved, health_changed
    )
    logger.info("alert run: %s", final)
    return final
