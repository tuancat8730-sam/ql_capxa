import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Header, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import Contract, Document, Package, ProgressLog, StagePlan, Task, User
from app.routers.packages import package_or_404
from app.schemas.common import Page, PaginationDep
from app.schemas.progress import (
    ProgressLogIn,
    ProgressLogOut,
    ProgressLogUpdate,
    StagePlanOut,
    StagePlanUpdate,
    StagesOut,
    StageStatus,
    StageUpdateOut,
    TaskIn,
    TaskOut,
    TaskUpdate,
    TimelineContract,
    TimelineOut,
    TimelinePackage,
    TimelineStage,
)
from app.services import audit
from app.services.finance import today_local
from app.services.progress import (
    STAGE_ORDER,
    all_tasks_done,
    effective_stage_status,
    ensure_stage_plans,
    recompute_package,
    stage_dates_valid,
    would_create_cycle,
)

router = APIRouter(tags=["progress"])

Reader = Annotated[User, Depends(require("progress", Level.READ))]
Writer = Annotated[User, Depends(require("progress", Level.WRITE))]
PackageReader = Annotated[User, Depends(require("package", Level.READ))]

_STAGE_TRACKED = tuple(StagePlanUpdate.model_fields)
_TASK_TRACKED = tuple(TaskUpdate.model_fields)
_LOG_TRACKED = tuple(ProgressLogUpdate.model_fields)
_TASK_NON_NULL = frozenset({"title", "status", "priority", "weight", "depends_on"})
_STAGE_NON_NULL = frozenset({"name", "progress_pct", "weight", "status"})


def _reject_nulls(changes: dict[str, Any], required: frozenset[str]) -> None:
    nulls = sorted(k for k, v in changes.items() if v is None and k in required)
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)


def _audit(
    session: AsyncSession,
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


# --- stages ----------------------------------------------------------------------------------


async def _task_counts(
    session: AsyncSession, package_id: uuid.UUID
) -> dict[uuid.UUID, tuple[int, int]]:
    rows = (
        await session.execute(
            select(Task.stage_plan_id, Task.status, func.count())
            .where(
                Task.package_id == package_id,
                Task.deleted_at.is_(None),
                Task.stage_plan_id.is_not(None),
            )
            .group_by(Task.stage_plan_id, Task.status)
        )
    ).all()
    counts: dict[uuid.UUID, tuple[int, int]] = {}
    for stage_id, status, n in rows:
        if stage_id is None:
            continue
        total, done = counts.get(stage_id, (0, 0))
        counts[stage_id] = (total + n, done + (n if status == "done" else 0))
    return counts


def _stage_out(
    stage: StagePlan, today: date, counts: dict[uuid.UUID, tuple[int, int]]
) -> StagePlanOut:
    out = StagePlanOut.model_validate(stage)
    out.effective_status = cast(
        StageStatus,
        effective_stage_status(stage.status, stage.planned_end, stage.progress_pct, today),
    )
    out.task_count, out.tasks_done = counts.get(stage.id, (0, 0))
    return out


async def _stages_out(session: AsyncSession, package: Package) -> StagesOut:
    stages = await ensure_stage_plans(session, package)
    await recompute_package(session, package)
    await session.commit()
    counts = await _task_counts(session, package.id)
    today = today_local()
    return StagesOut(
        package_progress=package.progress_pct,
        current_stage=package.current_stage,
        stages=[_stage_out(s, today, counts) for s in stages],
    )


@router.get("/packages/{package_id}/stages", response_model=StagesOut)
async def list_stages(package_id: uuid.UUID, _: Reader, session: SessionDep) -> StagesOut:
    return await _stages_out(session, await package_or_404(session, package_id))


@router.patch("/stage-plans/{stage_id}", response_model=StageUpdateOut)
async def update_stage(
    stage_id: uuid.UUID,
    body: StagePlanUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> StageUpdateOut:
    stage = await session.get(StagePlan, stage_id)
    if stage is None:
        raise AppError(404, "not_found", "Không tìm thấy giai đoạn")
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, _STAGE_NON_NULL)
    before = audit.snapshot(stage, _STAGE_TRACKED)
    for field, value in changes.items():
        setattr(stage, field, value)

    bad = stage_dates_valid(
        stage.planned_start, stage.planned_end, stage.actual_start, stage.actual_end
    )
    if bad:
        await session.rollback()
        raise AppError(422, "validation_error", "Ngày kết thúc không được trước ngày bắt đầu", bad)

    today = today_local()
    if stage.status == "done":
        stage.progress_pct = Decimal(100)
        stage.actual_end = stage.actual_end or today
        stage.actual_start = stage.actual_start or stage.actual_end
    elif stage.progress_pct >= 100 and "status" not in changes:
        stage.status = "done"
        stage.actual_end = stage.actual_end or today
    elif stage.progress_pct > 0 and stage.status == "not_started":
        stage.status = "in_progress"
        stage.actual_start = stage.actual_start or today
    stage.updated_by = user.id

    delta = audit.diff(before, audit.snapshot(stage, _STAGE_TRACKED))
    if delta:
        _audit(session, user, request, "update", "stage_plan", stage.id, delta)
    package = await session.get(Package, stage.package_id)
    assert package is not None
    await recompute_package(session, package)
    await session.commit()
    await session.refresh(stage)
    await session.refresh(package)
    counts = await _task_counts(session, package.id)
    return StageUpdateOut(
        stage=_stage_out(stage, today, counts),
        package_progress=package.progress_pct,
        current_stage=package.current_stage,
    )


# --- tasks -----------------------------------------------------------------------------------


async def _tasks(session: AsyncSession, package_id: uuid.UUID) -> list[Task]:
    return list(
        (
            await session.execute(
                select(Task)
                .where(Task.package_id == package_id, Task.deleted_at.is_(None))
                .order_by(Task.planned_end.nulls_last(), Task.created_at, Task.id)
            )
        )
        .scalars()
        .all()
    )


def _task_out(task: Task, all_tasks: list[Task]) -> TaskOut:
    out = TaskOut.model_validate(task)
    if task.stage_plan_id is not None:
        out.stage_all_done = all_tasks_done(
            t.status for t in all_tasks if t.stage_plan_id == task.stage_plan_id
        )
    return out


async def _validate_task(
    session: AsyncSession, package_id: uuid.UUID, task: Task | None, changes: dict[str, Any]
) -> None:
    if changes.get("stage_plan_id") is not None:
        stage = await session.get(StagePlan, changes["stage_plan_id"])
        if stage is None or stage.package_id != package_id:
            raise AppError(
                422, "validation_error", "Giai đoạn không thuộc gói này", ["stage_plan_id"]
            )
    if changes.get("assignee_id") is not None:
        assignee = await session.get(User, changes["assignee_id"])
        if assignee is None or not assignee.is_active:
            raise AppError(422, "validation_error", "Người phụ trách không hợp lệ", ["assignee_id"])
    start = changes.get("planned_start", task.planned_start if task else None)
    end = changes.get("planned_end", task.planned_end if task else None)
    if start and end and end < start:
        raise AppError(
            422, "validation_error", "Ngày kết thúc không được trước ngày bắt đầu", ["planned_end"]
        )
    if changes.get("depends_on"):
        wanted = set(changes["depends_on"])
        existing = {t.id: t for t in await _tasks(session, package_id)}
        if wanted - set(existing):
            raise AppError(
                422, "validation_error", "Công việc phụ thuộc không thuộc gói này", ["depends_on"]
            )
        edges = {tid: t.depends_on for tid, t in existing.items()}
        this_id = task.id if task else uuid.uuid4()
        if would_create_cycle(edges, this_id, wanted):
            raise AppError(422, "validation_error", "Phụ thuộc tạo thành vòng lặp", ["depends_on"])


def _apply_task_rules(task: Task, changes: dict[str, Any]) -> None:
    if changes.get("status") == "done" and task.actual_end is None:
        task.actual_end = today_local()


@router.get("/packages/{package_id}/tasks", response_model=list[TaskOut])
async def list_tasks(
    package_id: uuid.UUID,
    _: Reader,
    session: SessionDep,
    stage_plan_id: uuid.UUID | None = None,
    status: str | None = None,
    assignee_id: uuid.UUID | None = None,
) -> list[TaskOut]:
    await package_or_404(session, package_id)
    everything = await _tasks(session, package_id)
    rows = [
        t
        for t in everything
        if (stage_plan_id is None or t.stage_plan_id == stage_plan_id)
        and (status is None or t.status == status)
        and (assignee_id is None or t.assignee_id == assignee_id)
    ]
    return [_task_out(t, everything) for t in rows]


@router.post("/packages/{package_id}/tasks", response_model=TaskOut, status_code=201)
async def create_task(
    package_id: uuid.UUID, body: TaskIn, request: Request, user: Writer, session: SessionDep
) -> TaskOut:
    await package_or_404(session, package_id)
    data = body.model_dump(exclude_unset=True)
    _reject_nulls(data, _TASK_NON_NULL)
    await _validate_task(session, package_id, None, data)
    task = Task(package_id=package_id, created_by=user.id, updated_by=user.id, **data)
    _apply_task_rules(task, data)
    session.add(task)
    await session.flush()
    _audit(session, user, request, "create", "task", task.id, {"package_id": package_id, **data})
    await session.commit()
    await session.refresh(task)
    return _task_out(task, await _tasks(session, package_id))


async def _task_or_404(session: AsyncSession, task_id: uuid.UUID) -> Task:
    task = await session.get(Task, task_id)
    if task is None or task.deleted_at is not None:
        raise AppError(404, "not_found", "Không tìm thấy công việc")
    return task


@router.patch("/tasks/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: uuid.UUID, body: TaskUpdate, request: Request, user: Writer, session: SessionDep
) -> TaskOut:
    task = await _task_or_404(session, task_id)
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, _TASK_NON_NULL)
    await _validate_task(session, task.package_id, task, changes)
    before = audit.snapshot(task, _TASK_TRACKED)
    for field, value in changes.items():
        setattr(task, field, value)
    _apply_task_rules(task, changes)
    task.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(task, _TASK_TRACKED))
    if delta:
        _audit(session, user, request, "update", "task", task.id, delta)
    await session.commit()
    await session.refresh(task)
    return _task_out(task, await _tasks(session, task.package_id))


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    task_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    task = await _task_or_404(session, task_id)
    task.deleted_at = datetime.now(UTC)
    for other in await _tasks(session, task.package_id):
        if task.id in other.depends_on:
            other.depends_on = [d for d in other.depends_on if d != task.id]
    _audit(session, user, request, "delete", "task", task.id, {"title": task.title})
    await session.commit()
    return Response(status_code=204)


# --- daily progress logs -----------------------------------------------------------------------


async def _check_attachments(
    session: AsyncSession, package_id: uuid.UUID, ids: list[uuid.UUID] | None
) -> None:
    if not ids:
        return
    found = (
        (
            await session.execute(
                select(Document.id).where(
                    Document.id.in_(ids),
                    Document.deleted_at.is_(None),
                    Document.package_id == package_id,
                )
            )
        )
        .scalars()
        .all()
    )
    missing = [str(i) for i in set(ids) - set(found)]
    if missing:
        raise AppError(422, "validation_error", "Tệp đính kèm không thuộc gói này", missing)


async def _log_out(session: AsyncSession, log: ProgressLog) -> ProgressLogOut:
    author = await session.get(User, log.author_id)
    out = ProgressLogOut.model_validate(log)
    out.author_name = author.full_name if author else None
    out.attachments = [uuid.UUID(str(a)) for a in log.attachments]
    return out


@router.get("/packages/{package_id}/progress-logs", response_model=Page[ProgressLogOut])
async def list_logs(
    package_id: uuid.UUID,
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    date_from: date | None = None,
    date_to: date | None = None,
    author_id: uuid.UUID | None = None,
) -> Page[ProgressLogOut]:
    await package_or_404(session, package_id)
    stmt = select(ProgressLog).where(ProgressLog.package_id == package_id)
    if date_from:
        stmt = stmt.where(ProgressLog.log_date >= date_from)
    if date_to:
        stmt = stmt.where(ProgressLog.log_date <= date_to)
    if author_id:
        stmt = stmt.where(ProgressLog.author_id == author_id)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(ProgressLog.log_date.desc(), ProgressLog.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[ProgressLogOut](
        items=[await _log_out(session, r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/packages/{package_id}/progress-logs", response_model=ProgressLogOut, status_code=201)
async def create_log(
    package_id: uuid.UUID,
    body: ProgressLogIn,
    request: Request,
    response: Response,
    user: Writer,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> ProgressLogOut:
    await package_or_404(session, package_id)
    key = idempotency_key or body.client_id
    if key is not None and not 8 <= len(key) <= 64:
        raise AppError(
            422, "validation_error", "Idempotency-Key phải dài 8-64 ký tự", ["idempotency_key"]
        )
    if key:
        replay = (
            await session.execute(select(ProgressLog).where(ProgressLog.client_id == key))
        ).scalar_one_or_none()
        if replay is not None:
            if replay.package_id != package_id or replay.author_id != user.id:
                raise AppError(409, "conflict", "Idempotency-Key đã được dùng cho bản ghi khác")
            response.status_code = 200  # same request retried: return the first result
            return await _log_out(session, replay)

    if body.log_date > today_local() + timedelta(days=1):
        raise AppError(
            422, "validation_error", "Không thể ghi nhật ký cho ngày trong tương lai", ["log_date"]
        )
    existing = (
        await session.execute(
            select(ProgressLog).where(
                ProgressLog.package_id == package_id,
                ProgressLog.log_date == body.log_date,
                ProgressLog.author_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AppError(
            409,
            "log_exists",
            "Đã có nhật ký của bạn cho gói và ngày này",
            {"id": str(existing.id)},
        )
    await _check_attachments(session, package_id, body.attachments)

    data = body.model_dump(exclude={"client_id"})
    data["attachments"] = [str(a) for a in data.get("attachments") or []]
    log = ProgressLog(
        package_id=package_id,
        author_id=user.id,
        client_id=key,
        created_by=user.id,
        updated_by=user.id,
        **data,
    )
    session.add(log)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "log_exists", "Đã có nhật ký của bạn cho gói và ngày này") from exc
    _audit(
        session,
        user,
        request,
        "create",
        "progress_log",
        log.id,
        {"package_id": package_id, "log_date": body.log_date, "progress_pct": body.progress_pct},
    )
    await session.commit()
    await session.refresh(log)
    return await _log_out(session, log)


@router.patch("/progress-logs/{log_id}", response_model=ProgressLogOut)
async def update_log(
    log_id: uuid.UUID,
    body: ProgressLogUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> ProgressLogOut:
    log = await session.get(ProgressLog, log_id)
    if log is None:
        raise AppError(404, "not_found", "Không tìm thấy nhật ký")
    if log.author_id != user.id and user.role not in {"admin", "director"}:
        raise AppError(403, "forbidden", "Chỉ người viết hoặc quản lý mới được sửa nhật ký")
    changes = body.model_dump(exclude_unset=True)
    _reject_nulls(changes, frozenset({"progress_pct"}))
    await _check_attachments(session, log.package_id, changes.get("attachments"))
    if "attachments" in changes:
        changes["attachments"] = [str(a) for a in changes["attachments"] or []]
    before = audit.snapshot(log, changes)
    for field, value in changes.items():
        setattr(log, field, value)
    log.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(log, changes))
    if delta:
        _audit(session, user, request, "update", "progress_log", log.id, delta)
    await session.commit()
    await session.refresh(log)
    return await _log_out(session, log)


# --- timeline (Gantt) --------------------------------------------------------------------------


@router.get("/dashboard/timeline", response_model=TimelineOut)
async def timeline(_: PackageReader, session: SessionDep) -> TimelineOut:
    """Every package's stages and contract bar on one axis (SPEC 4.2 #8, 4.4 Gantt)."""
    today = today_local()
    packages = (
        (
            await session.execute(
                select(Package).where(Package.deleted_at.is_(None)).order_by(Package.number)
            )
        )
        .scalars()
        .all()
    )
    out: list[TimelinePackage] = []
    dates: list[date] = []
    for package in packages:
        stages = await ensure_stage_plans(session, package)
        contract = (
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
        timeline_contract = None
        if contract:
            start = contract.effective_date or contract.signed_date
            end = contract.extended_end_date or contract.planned_end_date
            timeline_contract = TimelineContract(
                contract_no=contract.contract_no,
                start=start,
                end=end,
                end_date_override=contract.end_date_override,
                extended_end_date=contract.extended_end_date,
            )
            dates += [d for d in (start, end) if d]
        for s in stages:
            dates += [
                d for d in (s.planned_start, s.planned_end, s.actual_start, s.actual_end) if d
            ]
        out.append(
            TimelinePackage(
                id=package.id,
                number=package.number,
                name=package.name,
                health=package.health,
                progress_pct=package.progress_pct,
                stages=[
                    TimelineStage(
                        id=s.id,
                        stage_code=s.stage_code,
                        name=s.name,
                        planned_start=s.planned_start,
                        planned_end=s.planned_end,
                        actual_start=s.actual_start,
                        actual_end=s.actual_end,
                        progress_pct=s.progress_pct,
                        effective_status=effective_stage_status(
                            s.status, s.planned_end, s.progress_pct, today
                        ),
                    )
                    for s in sorted(stages, key=lambda r: STAGE_ORDER.index(r.stage_code))
                ],
                contract=timeline_contract,
            )
        )
    await session.commit()
    return TimelineOut(
        today=today,
        range_start=min(dates) if dates else None,
        range_end=max(dates) if dates else None,
        packages=out,
    )
