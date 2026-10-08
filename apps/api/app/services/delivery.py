"""Assembles what the software-delivery pages show: task states, weeks, the overview."""

import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DecisionItem, Risk, WbsTask, WeeklyReport
from app.schemas.delivery import (
    AttentionItem,
    CurvePoint,
    DecisionOut,
    MilestoneNext,
    OverviewOut,
    PhaseSummary,
    ReportOut,
    TaskOut,
    WeekOut,
)
from app.services import delivery_rules as rules

VERY_HIGH_SCORE = 25  # 5 x 5: the "Rất cao" level of the risk list
MILESTONE_LOOKAHEAD_DAYS = 14


def view(task: WbsTask) -> rules.TaskView:
    return rules.TaskView(
        code=task.code,
        phase_code=task.phase_code,
        is_milestone=task.is_milestone,
        plan_start=task.plan_start,
        plan_end=task.plan_end,
        plan_days=task.plan_days,
        tracked=task.tracked,
        status=task.status,
        pct=task.pct,
    )


def display_code(task: WbsTask) -> str:
    """ "III-4" is written "III.4"; milestones keep their code ("M3")."""
    return task.code if task.is_milestone else task.code.replace("-", ".")


def dd(day: date) -> str:
    return f"{day:%d/%m}"


async def load_tasks(session: AsyncSession, project_id: uuid.UUID) -> list[WbsTask]:
    rows = await session.execute(
        select(WbsTask).where(WbsTask.project_id == project_id).order_by(WbsTask.sort_order)
    )
    return list(rows.scalars().all())


def task_out(task: WbsTask, today: date) -> TaskOut:
    out = TaskOut.model_validate(task)
    v = view(task)
    out.code = display_code(task)
    out.state = rules.task_state(v, today)
    out.late_days = rules.late_days(v, today) if out.state != "done" else 0
    return out


def decision_out(item: DecisionItem, today: date) -> DecisionOut:
    out = DecisionOut.model_validate(item)
    out.overdue = item.status == "pending" and item.due_date is not None and item.due_date < today
    return out


def _span(tasks: list[WbsTask]) -> tuple[date, date] | None:
    if not tasks:
        return None
    return min(t.plan_start for t in tasks), max(t.plan_end for t in tasks)


async def load_reports(session: AsyncSession, project_id: uuid.UUID) -> dict[date, WeeklyReport]:
    rows = await session.execute(select(WeeklyReport).where(WeeklyReport.project_id == project_id))
    return {r.week_start: r for r in rows.scalars()}


def week_state(week: rules.Week, report: WeeklyReport | None, today: date) -> str:
    if report is not None:
        return report.status
    if week.end < today:
        return "missing"
    return "current" if week.start <= today else "future"


async def build_weeks(session: AsyncSession, project_id: uuid.UUID, today: date) -> list[WeekOut]:
    tasks = await load_tasks(session, project_id)
    span = _span(tasks)
    if span is None:
        return []
    views = [view(t) for t in tasks]
    reports = await load_reports(session, project_id)
    actual_now = round(rules.actual_pct(views))
    out: list[WeekOut] = []
    for week in rules.report_weeks(*span):
        report = reports.get(week.start)
        out.append(
            WeekOut(
                no=week.no,
                start=week.start,
                end=week.end,
                state=week_state(week, report, today),
                report=ReportOut.model_validate(report) if report else None,
                suggested_planned_pct=round(rules.plan_pct_at(views, min(week.end, span[1]))),
                suggested_actual_pct=actual_now,
            )
        )
    return out


async def count_pending_decisions(session: AsyncSession, project_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(DecisionItem)
            .where(DecisionItem.project_id == project_id, DecisionItem.status == "pending")
        )
    ).scalar_one()


async def count_very_high_risks(session: AsyncSession, project_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(Risk)
            .where(
                Risk.project_id == project_id,
                Risk.status != "closed",
                Risk.score >= VERY_HIGH_SCORE,
            )
        )
    ).scalar_one()


def _task_item(t: WbsTask, today: date) -> AttentionItem | None:
    v = view(t)
    state = rules.task_state(v, today)
    title = f"{display_code(t)} · {t.name}"
    pct = rules.task_pct(v)
    common = {"title": title, "target": "task", "ref": str(t.id)}
    if state == "late":
        days = rules.late_days(v, today)
        if t.is_milestone:
            sub = f"Mốc {dd(t.plan_start)}, chưa đạt"
        else:
            sub = f"Hạn {dd(t.plan_end)}" + (f", quá {days} ngày làm việc" if days else "")
            sub += f" · hoàn thành {pct}%"
        return AttentionItem(rank=0, chip="bad", label="Trễ hạn", sub=sub, **common)
    if state == "behind":
        plan = round(rules.plan_fraction(v, today) * 100)
        sub = f"Hoàn thành {pct}%, kế hoạch đến nay {plan}%"
        return AttentionItem(rank=1, chip="warn", label="Chậm", sub=sub, **common)
    if state == "stale":
        sub = (
            f"Mốc {dd(t.plan_start)}"
            if t.is_milestone
            else f"Kế hoạch {dd(t.plan_start)}–{dd(t.plan_end)} · chưa có tiến độ"
        )
        return AttentionItem(rank=3, chip="stale", label="Cần cập nhật", sub=sub, **common)
    if (
        t.is_milestone
        and state == "todo"
        and (t.plan_start - today).days <= MILESTONE_LOOKAHEAD_DAYS
    ):
        n = (t.plan_start - today).days
        sub = dd(t.plan_start) + (f" · còn {n} ngày" if n > 0 else " · hôm nay")
        return AttentionItem(rank=2, chip="accent", label="Sắp đến mốc", sub=sub, **common)
    return None


def attention_items(
    tasks: list[WbsTask], weeks: list[WeekOut], pending: int, very_high: int, today: date
) -> list[AttentionItem]:
    out = [item for t in tasks if (item := _task_item(t, today)) is not None]
    for w in weeks:
        if w.state == "missing":
            out.append(
                AttentionItem(
                    rank=4,
                    chip="warn",
                    label="Báo cáo tuần",
                    title=f"Chưa nhận báo cáo tuần {w.no}",
                    sub=f"{dd(w.start)} – {dd(w.end)}",
                    target="week",
                    ref=w.start.isoformat(),
                )
            )
    if pending:
        out.append(
            AttentionItem(
                rank=5,
                chip="warn",
                label="Chờ CĐT",
                title=f"{pending} nội dung tồn đọng chờ Chủ đầu tư quyết định",
                sub="Mở mục Rủi ro & tồn đọng để xem từng việc",
                target="risks",
                ref="decisions",
            )
        )
    if very_high:
        out.append(
            AttentionItem(
                rank=6,
                chip="bad",
                label="Rủi ro",
                title=f"{very_high} rủi ro mức rất cao đang mở",
                sub="Mở mục Rủi ro & tồn đọng để xem biện pháp",
                target="risks",
                ref="risks",
            )
        )
    return sorted(out, key=lambda a: a.rank)


async def build_overview(session: AsyncSession, project_id: uuid.UUID, today: date) -> OverviewOut:
    tasks = await load_tasks(session, project_id)
    views = {t.id: view(t) for t in tasks}
    leaves = [views[t.id] for t in tasks if not t.is_milestone]
    span = _span(tasks)
    weeks = await build_weeks(session, project_id, today)
    pending = await count_pending_decisions(session, project_id)
    very_high = await count_very_high_risks(session, project_id)

    actual = rules.actual_pct(leaves)
    plan = rules.plan_pct_at(leaves, today)
    states = {t.id: rules.task_state(views[t.id], today) for t in tasks}

    milestones = sorted((t for t in tasks if t.is_milestone), key=lambda t: t.plan_start)
    upcoming = next((m for m in milestones if states[m.id] != "done"), None)

    phases: list[PhaseSummary] = []
    for code in dict.fromkeys(t.phase_code for t in tasks):
        in_phase = [t for t in tasks if t.phase_code == code]
        phase_leaves = [views[t.id] for t in in_phase if not t.is_milestone]
        start = min(t.plan_start for t in in_phase)
        phases.append(
            PhaseSummary(
                code=code,
                name=in_phase[0].phase_name,
                start=start,
                end=max(t.plan_end for t in in_phase),
                actual_pct=rules.actual_pct(phase_leaves) if phase_leaves else 0,
                plan_pct=rules.plan_pct_at(phase_leaves, today) if phase_leaves else 0,
                state=rules.phase_state([states[t.id] for t in in_phase], start, today),
            )
        )

    curve: list[CurvePoint] = []
    points: list[CurvePoint] = []
    if span:
        day = span[0]
        while day <= span[1]:
            curve.append(CurvePoint(date=day, pct=round(rules.plan_pct_at(leaves, day), 2)))
            day += timedelta(days=1)
        reports = await load_reports(session, project_id)
        for week in rules.report_weeks(*span):
            report = reports.get(week.start)
            if report is not None and report.actual_pct is not None:
                points.append(CurvePoint(date=min(week.end, span[1]), pct=report.actual_pct))

    ended = [w for w in weeks if w.end < today]
    return OverviewOut(
        today=today,
        project_start=span[0] if span else None,
        project_end=span[1] if span else None,
        has_progress=any(t.tracked for t in tasks),
        actual_pct=round(actual, 1),
        plan_pct=round(plan, 1),
        diff=round(actual - plan),
        next_milestone=(
            MilestoneNext(
                id=upcoming.id,
                code=upcoming.code,
                name=upcoming.name,
                date=upcoming.plan_start,
                days_left=(upcoming.plan_start - today).days,
            )
            if upcoming
            else None
        ),
        late_count=sum(1 for s in states.values() if s in {"late", "behind"}),
        stale_count=sum(1 for s in states.values() if s == "stale"),
        weeks_ended=len(ended),
        weeks_received=sum(1 for w in ended if w.report is not None),
        pending_decisions=pending,
        attention=attention_items(tasks, weeks, pending, very_high, today),
        phases=phases,
        plan_curve=curve,
        report_points=points,
    )
