"""Sync milestones (section V) into `tasks` and issues (section VI) into `risks`.

Identity is the key the reader gives each row: `tasks.source_key` (unique per package) and
`risks.code` (unique per project). A row that disappears from the workbook is reported as
`missing_in_workbook`; it is not deleted, so the user decides what happens to it.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Package, Project, Risk, Task
from app.services.risk_rules import risk_score
from app.services.tracking_changes import Change, set_fields
from app.services.tracking_details import (
    DetailSnapshot,
    IssueRow,
    MilestoneRow,
    first_date,
    last_date,
)
from app.services.tracking_mapping import (
    issue_status,
    priority_score,
    risk_category,
    task_status,
)
from app.services.tracking_workbook import SEVERITY_WARNING, Finding

WORKBOOK_SOURCE = "workbook"


def milestone_key(row: MilestoneRow) -> str:
    return f"M{row.package_code}-{row.seq:02d}"


def issue_code(row: IssueRow) -> str:
    return f"WB{row.package_code}-V{row.seq:02d}"


def _iso_to_date(text: str | None) -> date | None:
    return None if text is None else date.fromisoformat(text)


def _milestone_values(row: MilestoneRow, status: str | None) -> dict[str, Any]:
    """A single date in the timing cell is the planned end; two or more give start and end."""
    first, last = first_date(row.timing), last_date(row.timing)
    start = None if first == last else first
    notes = " | ".join(part for part in (row.result, row.documents, row.unit, row.note) if part)
    return {
        "title": row.title or None,
        "planned_start": _iso_to_date(start),
        "planned_end": _iso_to_date(last),
        "status": status,
        "notes": notes or None,
    }


async def _sync_task(
    session: AsyncSession, package: Package, row: MilestoneRow
) -> tuple[Change, str | None]:
    """Return the change and the workbook status text when it was not recognised."""
    key = milestone_key(row)
    status = task_status(row.status)
    values = _milestone_values(row, status)
    unknown = None if status else row.status
    existing = (
        await session.execute(
            select(Task).where(Task.package_id == package.id, Task.source_key == key)
        )
    ).scalar_one_or_none()
    if existing is None:
        obj = Task(package_id=package.id, source_key=key, priority="normal")
        session.add(obj)
        created = set_fields(obj, values)
        await session.flush()
        return Change("task", key, "create", created), unknown
    changed = set_fields(existing, values)
    return Change("task", key, "update" if changed else "unchanged", changed), unknown


def _risk_values(row: IssueRow, package: Package, probability: int, impact: int) -> dict[str, Any]:
    return {
        "title": row.title or None,
        "description": row.cause or None,
        "category": risk_category(row.title),
        "probability": probability,
        "impact": impact,
        "score": risk_score(probability, impact),
        "owner_text": row.unit or None,
        "mitigation": row.proposal or None,
        "note": row.basis or None,
        "status": issue_status(row.status) or "open",
        "source": WORKBOOK_SOURCE,
        "package_id": package.id,
    }


async def _sync_risk(
    session: AsyncSession, project: Project, package: Package, row: IssueRow
) -> Change | None:
    """Return None (and leave the database alone) when the priority is not recognised."""
    code = issue_code(row)
    scored = priority_score(row.priority)
    if scored is None:
        return None
    values = _risk_values(row, package, *scored)
    existing = (
        await session.execute(select(Risk).where(Risk.project_id == project.id, Risk.code == code))
    ).scalar_one_or_none()
    now = datetime.now(UTC)
    if existing is None:
        obj = Risk(project_id=project.id, code=code, last_reviewed_at=now)
        session.add(obj)
        created = set_fields(obj, values)
        await session.flush()
        return Change("risk", code, "create", created)
    changed = set_fields(existing, values)
    if changed:
        existing.last_reviewed_at = now
    return Change("risk", code, "update" if changed else "unchanged", changed)


async def _missing_tasks(
    session: AsyncSession, packages: dict[str, Package], seen: set[str]
) -> list[Change]:
    ids = [package.id for package in packages.values()]
    if not ids:
        return []
    keys = (
        await session.execute(
            select(Task.source_key).where(Task.package_id.in_(ids), Task.source_key.is_not(None))
        )
    ).scalars()
    return [
        Change("task", key, "missing_in_workbook")
        for key in keys
        if key is not None and key not in seen
    ]


async def _missing_risks(session: AsyncSession, project: Project, seen: set[str]) -> list[Change]:
    codes = (
        await session.execute(
            select(Risk.code).where(Risk.project_id == project.id, Risk.source == WORKBOOK_SOURCE)
        )
    ).scalars()
    return [Change("risk", code, "missing_in_workbook") for code in codes if code not in seen]


async def sync_items(
    session: AsyncSession,
    project: Project,
    packages: dict[str, Package],
    details: DetailSnapshot,
) -> tuple[list[Change], list[str], list[Finding]]:
    """Return (changes, wording the mapping did not recognise, findings)."""
    changes: list[Change] = []
    unmapped: list[str] = []
    findings: list[Finding] = []
    seen_tasks: set[str] = set()
    seen_risks: set[str] = set()
    for row in details.milestones:
        package = packages.get(row.package_code)
        if package is None:
            findings.append(
                Finding(
                    SEVERITY_WARNING, "milestone_no_package", f"{milestone_key(row)}: không có gói"
                )
            )
            continue
        change, unknown = await _sync_task(session, package, row)
        changes.append(change)
        seen_tasks.add(milestone_key(row))
        if unknown:
            unmapped.append(f"mốc {milestone_key(row)}: trạng thái [{unknown}]")
    for issue in details.issues:
        package = packages.get(issue.package_code)
        if package is None:
            findings.append(
                Finding(SEVERITY_WARNING, "issue_no_package", f"{issue_code(issue)}: không có gói")
            )
            continue
        seen_risks.add(issue_code(issue))
        risk_change = await _sync_risk(session, project, package, issue)
        if risk_change is None:
            unmapped.append(f"{issue_code(issue)}: mức ưu tiên [{issue.priority or 'trống'}]")
            continue
        changes.append(risk_change)
    changes.extend(await _missing_tasks(session, packages, seen_tasks))
    changes.extend(await _missing_risks(session, project, seen_risks))
    return changes, unmapped, findings
