"""Software-delivery projects: the schedule (WBS), weekly reports and open decisions."""

import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import ProjectDep, SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import DecisionItem, Project, Risk, User, WbsTask, WeeklyReport
from app.schemas.delivery import (
    DecisionIn,
    DecisionOut,
    DecisionUpdate,
    OverviewOut,
    ReportIn,
    ReportOut,
    TaskOut,
    TaskUpdate,
    WeekOut,
)
from app.services import audit
from app.services import delivery as svc
from app.services import delivery_rules as rules
from app.services.finance import today_local

router = APIRouter(prefix="/delivery", tags=["delivery"])

TaskReader = Annotated[User, Depends(require("wbs", Level.READ))]
TaskWriter = Annotated[User, Depends(require("wbs", Level.WRITE))]
ReportReader = Annotated[User, Depends(require("weekly_report", Level.READ))]
ReportWriter = Annotated[User, Depends(require("weekly_report", Level.WRITE))]
DecisionReader = Annotated[User, Depends(require("decision", Level.READ))]
DecisionWriter = Annotated[User, Depends(require("decision", Level.WRITE))]

_TASK_TRACKED = ("tracked", "status", "pct", "actual_start", "actual_end", "note")
_REPORT_TRACKED = (
    "report_no",
    "status",
    "submitted_on",
    "link",
    "planned_pct",
    "actual_pct",
    "done",
    "issues",
    "recommendations",
    "next_plan",
    "risk_ids",
)
_DECISION_TRACKED = ("no", "title", "reason", "status", "due_date", "decision", "decided_on")


def _delivery_project(project: ProjectDep) -> Project:
    if project.project_type != "software_delivery":
        raise AppError(404, "not_found", "Chức năng này không áp dụng cho loại dự án này")
    return project


DeliveryProject = Annotated[Project, Depends(_delivery_project)]


def _audit(
    session: SessionDep,
    user: User,
    request: Request,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    changes: dict[str, Any],
) -> None:
    audit.record(
        session,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user.id,
        changes=changes,
        request=request,
    )


# --- schedule ---------------------------------------------------------------------------------


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(_: TaskReader, session: SessionDep, project: DeliveryProject) -> list[TaskOut]:
    today = today_local()
    return [svc.task_out(t, today) for t in await svc.load_tasks(session, project.id)]


async def _task_or_404(session: SessionDep, project: Project, task_id: uuid.UUID) -> WbsTask:
    task = await session.get(WbsTask, task_id)
    if task is None or task.project_id != project.id:
        raise AppError(404, "not_found", "Không tìm thấy đầu việc")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdate,
    request: Request,
    user: TaskWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> TaskOut:
    """Record progress on a line. The entry is made consistent (see `normalise_update`)."""
    task = await _task_or_404(session, project, task_id)
    changes = body.model_dump(exclude_unset=True)
    today = today_local()
    before = audit.snapshot(task, _TASK_TRACKED)
    status, pct, started, ended = rules.normalise_update(
        is_milestone=task.is_milestone,
        plan_start=task.plan_start,
        plan_end=task.plan_end,
        status=changes.get("status") or task.status,
        pct=changes["pct"] if changes.get("pct") is not None else task.pct,
        actual_start=changes.get("actual_start", task.actual_start),
        actual_end=changes.get("actual_end", task.actual_end),
        today=today,
    )
    if started and ended and ended < started:
        raise AppError(
            422, "validation_error", "Ngày kết thúc thực tế trước ngày bắt đầu", ["actual_end"]
        )
    task.tracked = True
    task.status, task.pct, task.actual_start, task.actual_end = status, pct, started, ended
    if "note" in changes:
        task.note = changes["note"] or None
    task.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(task, _TASK_TRACKED))
    if delta:
        _audit(session, user, request, "update", "wbs_task", task.id, delta)
    await session.commit()
    await session.refresh(task)
    return svc.task_out(task, today)


@router.post("/tasks/{task_id}/reset", response_model=TaskOut)
async def reset_task(
    task_id: uuid.UUID,
    request: Request,
    user: TaskWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> TaskOut:
    """Forget the progress recorded on a line (back to "not updated yet")."""
    task = await _task_or_404(session, project, task_id)
    before = audit.snapshot(task, _TASK_TRACKED)
    task.tracked, task.status, task.pct = False, "not_started", 0
    task.actual_start = task.actual_end = task.note = None
    task.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(task, _TASK_TRACKED))
    if delta:
        _audit(session, user, request, "update", "wbs_task", task.id, delta)
    await session.commit()
    await session.refresh(task)
    return svc.task_out(task, today_local())


@router.get("/overview", response_model=OverviewOut)
async def overview(_: TaskReader, session: SessionDep, project: DeliveryProject) -> OverviewOut:
    return await svc.build_overview(session, project.id, today_local())


# --- weekly reports ---------------------------------------------------------------------------


@router.get("/weeks", response_model=list[WeekOut])
async def list_weeks(
    _: ReportReader, session: SessionDep, project: DeliveryProject
) -> list[WeekOut]:
    return await svc.build_weeks(session, project.id, today_local())


async def _check_risks(session: SessionDep, project: Project, ids: list[uuid.UUID]) -> None:
    if not ids:
        return
    found = set(
        (
            await session.execute(
                select(Risk.id).where(Risk.project_id == project.id, Risk.id.in_(ids))
            )
        )
        .scalars()
        .all()
    )
    if missing := set(ids) - found:
        raise AppError(
            422, "validation_error", "Rủi ro không thuộc dự án", sorted(str(i) for i in missing)
        )


@router.put("/reports/{week_start}", response_model=ReportOut)
async def save_report(
    week_start: date,
    body: ReportIn,
    request: Request,
    user: ReportWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> ReportOut:
    """Record (or correct) the report received for the period that starts on `week_start`."""
    weeks = await svc.build_weeks(session, project.id, today_local())
    if week_start not in {w.start for w in weeks}:
        raise AppError(422, "validation_error", "Không có kỳ báo cáo bắt đầu ngày này")
    await _check_risks(session, project, body.risk_ids)
    data = body.model_dump()
    data["risk_ids"] = [str(i) for i in body.risk_ids]
    report = (
        await session.execute(
            select(WeeklyReport).where(
                WeeklyReport.project_id == project.id, WeeklyReport.week_start == week_start
            )
        )
    ).scalar_one_or_none()
    before: dict[str, object] = {}
    if report is None:
        report = WeeklyReport(
            project_id=project.id, week_start=week_start, created_by=user.id, **data
        )
        session.add(report)
        action = "create"
    else:
        before = audit.snapshot(report, _REPORT_TRACKED)
        for field, value in data.items():
            setattr(report, field, value)
        action = "update"
    report.updated_by = user.id
    await session.flush()
    delta = audit.diff(before, audit.snapshot(report, _REPORT_TRACKED))
    if delta:
        _audit(session, user, request, action, "weekly_report", report.id, delta)
    await session.commit()
    await session.refresh(report)
    return ReportOut.model_validate(report)


@router.delete("/reports/{week_start}", status_code=204)
async def delete_report(
    week_start: date,
    request: Request,
    user: ReportWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> Response:
    report = (
        await session.execute(
            select(WeeklyReport).where(
                WeeklyReport.project_id == project.id, WeeklyReport.week_start == week_start
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise AppError(404, "not_found", "Chưa có báo cáo cho kỳ này")
    _audit(
        session,
        user,
        request,
        "delete",
        "weekly_report",
        report.id,
        {"week_start": week_start.isoformat()},
    )
    await session.delete(report)
    await session.commit()
    return Response(status_code=204)


# --- open decisions ---------------------------------------------------------------------------


async def _decision_or_404(
    session: SessionDep, project: Project, decision_id: uuid.UUID
) -> DecisionItem:
    item = await session.get(DecisionItem, decision_id)
    if item is None or item.project_id != project.id:
        raise AppError(404, "not_found", "Không tìm thấy mục tồn đọng")
    return item


@router.get("/decisions", response_model=list[DecisionOut])
async def list_decisions(
    _: DecisionReader, session: SessionDep, project: DeliveryProject
) -> list[DecisionOut]:
    today = today_local()
    rows = await session.execute(
        select(DecisionItem).where(DecisionItem.project_id == project.id).order_by(DecisionItem.no)
    )
    return [svc.decision_out(d, today) for d in rows.scalars()]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
async def create_decision(
    body: DecisionIn,
    request: Request,
    user: DecisionWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> DecisionOut:
    data = body.model_dump()
    if data["no"] is None:
        last = (
            await session.execute(
                select(func.coalesce(func.max(DecisionItem.no), 0)).where(
                    DecisionItem.project_id == project.id
                )
            )
        ).scalar_one()
        data["no"] = last + 1
    today = today_local()
    if data["status"] == "decided" and data["decided_on"] is None:
        data["decided_on"] = today
    item = DecisionItem(project_id=project.id, created_by=user.id, updated_by=user.id, **data)
    session.add(item)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "conflict", "Số thứ tự đã được dùng") from exc
    _audit(
        session,
        user,
        request,
        "create",
        "decision_item",
        item.id,
        audit.snapshot(item, _DECISION_TRACKED),
    )
    await session.commit()
    await session.refresh(item)
    return svc.decision_out(item, today)


@router.patch("/decisions/{decision_id}", response_model=DecisionOut)
async def update_decision(
    decision_id: uuid.UUID,
    body: DecisionUpdate,
    request: Request,
    user: DecisionWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> DecisionOut:
    item = await _decision_or_404(session, project, decision_id)
    changes = body.model_dump(exclude_unset=True)
    for required in ("title", "status", "no"):
        if required in changes and changes[required] is None:
            raise AppError(
                422, "validation_error", "Trường bắt buộc không được để trống", [required]
            )
    today = today_local()
    before = audit.snapshot(item, _DECISION_TRACKED)
    for field, value in changes.items():
        setattr(item, field, value)
    if changes.get("status") == "decided" and item.decided_on is None:
        item.decided_on = today
    item.updated_by = user.id
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "conflict", "Số thứ tự đã được dùng") from exc
    delta = audit.diff(before, audit.snapshot(item, _DECISION_TRACKED))
    if delta:
        _audit(session, user, request, "update", "decision_item", item.id, delta)
    await session.commit()
    await session.refresh(item)
    return svc.decision_out(item, today)


@router.delete("/decisions/{decision_id}", status_code=204)
async def delete_decision(
    decision_id: uuid.UUID,
    request: Request,
    user: DecisionWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> Response:
    item = await _decision_or_404(session, project, decision_id)
    _audit(
        session,
        user,
        request,
        "delete",
        "decision_item",
        item.id,
        audit.snapshot(item, _DECISION_TRACKED),
    )
    await session.delete(item)
    await session.commit()
    return Response(status_code=204)
