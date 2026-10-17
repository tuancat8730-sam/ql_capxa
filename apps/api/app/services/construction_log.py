"""Construction logs: the weeks they cover, checks against the schedule, saving and history."""

import hashlib
import json
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import (
    ConstructionLog,
    ConstructionLogCarryover,
    ConstructionLogEntry,
    ConstructionLogMemberWork,
    WbsTask,
)
from app.schemas.construction_log import (
    HistoryOut,
    LogIn,
    LogOut,
    LogWeekOut,
)
from app.services import delivery_rules as rules
from app.services.delivery import load_reports, load_tasks

HEADER_FIELDS = (
    "report_date",
    "recipients",
    "reporter_org",
    "contract_ref",
    "coordinator",
    "environment_note",
    "overall_status",
    "key_results",
    "issues",
    "coordination_requests",
    "related_report",
)


LINE_FIELDS: dict[str, tuple[str, ...]] = {
    "entries": (
        "entry_date",
        "phase_code",
        "task_code",
        "content",
        "personnel",
        "note",
        "state",
        "delay_days",
    ),
    "carryovers": ("phase_code", "task_code", "title", "result_to_date", "next_week", "note"),
    "member_work": (
        "member_name",
        "item",
        "plan_ref",
        "personnel",
        "result",
        "next_plan",
        "issues_actions",
    ),
}


def periods(tasks: list[WbsTask]) -> list[rules.Week]:
    """The reporting weeks of the project: the same 7-day periods as the weekly reports."""
    if not tasks:
        return []
    return rules.report_weeks(min(t.plan_start for t in tasks), max(t.plan_end for t in tasks))


async def load_log(
    session: AsyncSession, project_id: uuid.UUID, week_start: date, *, lock: bool = False
) -> ConstructionLog | None:
    """The log of a week with its lines; `lock` holds the row until the transaction ends."""
    query = (
        select(ConstructionLog)
        .where(ConstructionLog.project_id == project_id, ConstructionLog.week_start == week_start)
        .options(
            selectinload(ConstructionLog.entries),
            selectinload(ConstructionLog.carryovers),
            selectinload(ConstructionLog.member_work),
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update(of=ConstructionLog)
    return (await session.execute(query)).scalar_one_or_none()


def log_out(log: ConstructionLog) -> LogOut:
    return LogOut.model_validate(
        {
            **{c.name: getattr(log, c.name) for c in ConstructionLog.__table__.columns},
            "week_end": log.week_start + timedelta(days=rules.REPORT_DAYS - 1),
            "entries": log.entries,
            "carryovers": log.carryovers,
            "member_work": log.member_work,
        },
        from_attributes=True,
    )


async def build_week_list(session: AsyncSession, project_id: uuid.UUID) -> list[LogWeekOut]:
    tasks = await load_tasks(session, project_id)
    logs = {
        log.week_start: log
        for log in (
            await session.execute(
                select(ConstructionLog)
                .where(ConstructionLog.project_id == project_id)
                .options(selectinload(ConstructionLog.entries))
            )
        ).scalars()
    }
    reports = await load_reports(session, project_id)
    out: list[LogWeekOut] = []
    for week in periods(tasks):
        log = logs.get(week.start)
        delays = [e.delay_days or 0 for e in log.entries] if log else []
        out.append(
            LogWeekOut(
                no=week.no,
                week_start=week.start,
                week_end=week.end,
                has_log=log is not None,
                has_report=week.start in reports,
                report_date=log.report_date if log else None,
                entry_count=len(log.entries) if log else 0,
                max_delay_days=max(delays, default=0),
            )
        )
    return out


def _invalid(message: str, field: str) -> AppError:
    return AppError(422, "validation_error", message, [field])


def check_body(body: LogIn, week: rules.Week, tasks: list[WbsTask]) -> None:
    """Dates must fall in the week; a task code must exist and sit under the phase on the line."""
    phase_of = {t.code: t.phase_code for t in tasks}
    phases = set(phase_of.values())

    def check_task(phase: str, code: str | None, field: str) -> None:
        if phase not in phases:
            raise _invalid(f"Giai đoạn không có trong kế hoạch: {phase}", field)
        if code is None:
            return
        if code not in phase_of:
            raise _invalid(f"Mã đầu việc không có trong kế hoạch: {code}", field)
        if phase_of[code] != phase:
            raise _invalid(f"Đầu việc {code} không thuộc giai đoạn {phase}", field)

    for i, e in enumerate(body.entries):
        if not week.start <= e.entry_date <= week.end:
            raise _invalid("Ngày ghi nằm ngoài tuần của nhật ký", f"entries.{i}.entry_date")
        check_task(e.phase_code, e.task_code, f"entries.{i}.task_code")
    for i, c in enumerate(body.carryovers):
        check_task(c.phase_code, c.task_code, f"carryovers.{i}.task_code")


def apply_body(log: ConstructionLog, body: LogIn) -> None:
    """Write the header and replace every child line, numbering them in the order sent."""
    for field in HEADER_FIELDS:
        setattr(log, field, getattr(body, field))
    log.entries = [
        ConstructionLogEntry(seq=i, **e.model_dump()) for i, e in enumerate(body.entries)
    ]
    log.carryovers = [
        ConstructionLogCarryover(seq=i, **c.model_dump()) for i, c in enumerate(body.carryovers)
    ]
    log.member_work = [
        ConstructionLogMemberWork(seq=i, **m.model_dump()) for i, m in enumerate(body.member_work)
    ]


def _digest(rows: list[Any], fields: tuple[str, ...]) -> str:
    """A short fingerprint of the lines in order: any edit, addition or move changes it."""
    data = [[str(getattr(r, f)) for f in fields] for r in rows]
    return hashlib.sha256(json.dumps(data, ensure_ascii=False).encode()).hexdigest()[:12]


def audit_view(log: ConstructionLog) -> dict[str, object]:
    """What the audit row compares: the header, and a count and fingerprint of each kind of line."""
    view: dict[str, object] = {f: getattr(log, f) for f in HEADER_FIELDS}
    for name, fields in LINE_FIELDS.items():
        rows = getattr(log, name)
        view[name] = len(rows)
        view[f"{name}_digest"] = _digest(rows, fields)
    return view


async def task_history(
    session: AsyncSession, project_id: uuid.UUID, task_code: str
) -> list[HistoryOut]:
    rows = await session.execute(
        select(ConstructionLog.week_start, ConstructionLogEntry)
        .join(ConstructionLogEntry, ConstructionLogEntry.log_id == ConstructionLog.id)
        .where(
            ConstructionLog.project_id == project_id, ConstructionLogEntry.task_code == task_code
        )
        .order_by(ConstructionLogEntry.entry_date, ConstructionLogEntry.seq)
    )
    return [
        HistoryOut(
            week_start=week_start,
            entry_date=e.entry_date,
            content=e.content,
            note=e.note,
            state=e.state,
            delay_days=e.delay_days,
            personnel=list(e.personnel),
        )
        for week_start, e in rows.all()
    ]
