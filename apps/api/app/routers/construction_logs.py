"""The contractor's weekly construction log of a software-delivery project."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.exc import IntegrityError

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import ConstructionLog, User
from app.routers.delivery import DeliveryProject
from app.schemas.construction_log import HistoryOut, LogIn, LogOut, LogWeekOut
from app.services import audit
from app.services import construction_log as svc
from app.services.delivery import load_tasks

router = APIRouter(prefix="/delivery", tags=["construction-log"])

LogReader = Annotated[User, Depends(require("construction_log", Level.READ))]
LogWriter = Annotated[User, Depends(require("construction_log", Level.WRITE))]


@router.get("/logs", response_model=list[LogWeekOut])
async def list_log_weeks(
    _: LogReader, session: SessionDep, project: DeliveryProject
) -> list[LogWeekOut]:
    return await svc.build_week_list(session, project.id)


@router.get("/logs/{week_start}", response_model=LogOut)
async def get_log(
    week_start: date, _: LogReader, session: SessionDep, project: DeliveryProject
) -> LogOut:
    log = await svc.load_log(session, project.id, week_start)
    if log is None:
        raise AppError(404, "not_found", "Chưa có nhật ký cho tuần này")
    return svc.log_out(log)


@router.put("/logs/{week_start}", response_model=LogOut)
async def save_log(
    week_start: date,
    body: LogIn,
    request: Request,
    user: LogWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> LogOut:
    """Create or replace the log of the reporting week that starts on `week_start`."""
    tasks = await load_tasks(session, project.id)
    week = next((w for w in svc.periods(tasks) if w.start == week_start), None)
    if week is None:
        raise AppError(422, "validation_error", "Không có kỳ báo cáo bắt đầu ngày này")
    svc.check_body(body, week, tasks)

    log = await svc.load_log(session, project.id, week_start, lock=True)
    before: dict[str, object] = {}
    if log is None:
        log = ConstructionLog(project_id=project.id, week_start=week_start, created_by=user.id)
        session.add(log)
        action = "create"
    else:
        if body.expected_updated_at != log.updated_at:
            raise AppError(
                409, "log_changed", "Nhật ký đã được người khác sửa; tải lại trước khi lưu"
            )
        before = svc.audit_view(log)
        action = "update"
    svc.apply_body(log, body)
    log.updated_by = user.id
    log.updated_at = datetime.now(UTC)  # a change to the lines alone must move it too
    try:
        await session.flush()
    except IntegrityError:  # someone created the same week a moment ago
        await session.rollback()
        raise AppError(
            409, "log_changed", "Nhật ký đã được người khác tạo; tải lại trước khi lưu"
        ) from None
    delta = audit.diff(before, svc.audit_view(log))
    if delta:
        audit.record(
            session,
            action=action,
            entity_type="construction_log",
            entity_id=log.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    saved = await svc.load_log(session, project.id, week_start)
    assert saved is not None
    return svc.log_out(saved)


@router.delete("/logs/{week_start}", status_code=204)
async def delete_log(
    week_start: date,
    request: Request,
    user: LogWriter,
    session: SessionDep,
    project: DeliveryProject,
) -> Response:
    log = await svc.load_log(session, project.id, week_start)
    if log is None:
        raise AppError(404, "not_found", "Chưa có nhật ký cho tuần này")
    audit.record(
        session,
        action="delete",
        entity_type="construction_log",
        entity_id=log.id,
        user_id=user.id,
        changes={"week_start": week_start.isoformat()},
        request=request,
    )
    await session.delete(log)
    await session.commit()
    return Response(status_code=204)


@router.get("/tasks/{task_code}/log-history", response_model=list[HistoryOut])
async def task_log_history(
    task_code: str, _: LogReader, session: SessionDep, project: DeliveryProject
) -> list[HistoryOut]:
    """Every log line written about one schedule task, oldest first."""
    tasks = await load_tasks(session, project.id)
    if task_code not in {t.code for t in tasks}:
        raise AppError(404, "not_found", "Không tìm thấy đầu việc")
    return await svc.task_history(session, project.id, task_code)
