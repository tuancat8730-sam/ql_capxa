import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import SessionDep, require, require_roles
from app.core.errors import AppError
from app.core.rbac import Level, can
from app.core.scope import current_project_id
from app.models import Holiday, Issue, IssueEvent, Package, User
from app.routers.risks import next_code
from app.schemas.common import Page, PaginationDep
from app.schemas.risk import (
    EscalateIn,
    HolidayIn,
    HolidayOut,
    IssueDetail,
    IssueEventOut,
    IssueIn,
    IssueOut,
    IssueUpdate,
    ResolveIn,
)
from app.services import audit
from app.services.risk_rules import compute_due_at, is_overdue, overdue_days

router = APIRouter(tags=["issues"])

Reader = Annotated[User, Depends(require("risk", Level.READ))]
Writer = Annotated[User, Depends(require("risk", Level.WRITE))]
Admin = Annotated[User, Depends(require_roles("admin"))]

# Status moves a user may make with PATCH; resolved/escalated have dedicated endpoints.
_TRANSITIONS: dict[str, frozenset[str]] = {
    "open": frozenset({"in_progress"}),
    "in_progress": frozenset({"open"}),
    "escalated": frozenset({"in_progress", "open"}),
    "resolved": frozenset({"closed", "open"}),
    "closed": frozenset({"open"}),
}
_FINISHED = frozenset({"resolved", "closed"})


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def _now() -> datetime:
    return datetime.now(UTC)


async def _holidays(session: AsyncSession) -> set[date]:
    return set((await session.execute(select(Holiday.day))).scalars().all())


def _out(issue: Issue, now: datetime | None = None) -> IssueOut:
    now = now or _now()
    out = IssueOut.model_validate(issue)
    out.overdue = is_overdue(issue.due_at, issue.status, now)
    out.overdue_days = overdue_days(issue.due_at, issue.status, now)
    return out


async def _issue_or_404(session: AsyncSession, issue_id: uuid.UUID) -> Issue:
    issue = await session.get(Issue, issue_id)
    if issue is None or issue.project_id != current_project_id():
        raise AppError(404, "not_found", "Không tìm thấy vướng mắc")
    return issue


def _event(
    session: AsyncSession,
    issue: Issue,
    user: User,
    event: str,
    *,
    from_level: int | None = None,
    to_level: int | None = None,
    note: str | None = None,
) -> None:
    session.add(
        IssueEvent(
            issue_id=issue.id,
            user_id=user.id,
            event=event,
            from_level=from_level,
            to_level=to_level,
            note=note,
        )
    )


def _audit(
    session: AsyncSession,
    user: User,
    request: Request,
    action: str,
    issue: Issue,
    changes: dict[str, Any],
) -> None:
    audit.record(
        session,
        action=action,
        entity_type="issue",
        entity_id=issue.id,
        user_id=user.id,
        changes=changes,
        request=request,
    )


async def _check_refs(
    session: AsyncSession, package_id: uuid.UUID | None, assignee: uuid.UUID | None
) -> None:
    if package_id is not None:
        package = await session.get(Package, package_id)
        if package is None or package.project_id != current_project_id():
            raise AppError(422, "validation_error", "Gói thầu không tồn tại", ["package_id"])
    if assignee is not None:
        user = await session.get(User, assignee)
        if user is None or not user.is_active:
            raise AppError(422, "validation_error", "Người xử lý không hợp lệ", ["assigned_to"])


@router.get("/issues", response_model=Page[IssueOut])
async def list_issues(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    package_id: uuid.UUID | None = None,
    status: str | None = None,
    level: Annotated[int | None, Query(ge=1, le=3)] = None,
    issue_type: str | None = None,
    assigned_to: uuid.UUID | None = None,
    overdue: bool | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[IssueOut]:
    stmt = select(Issue).where(Issue.project_id == current_project_id())
    for column, value in (
        (Issue.package_id, package_id),
        (Issue.status, status),
        (Issue.level, level),
        (Issue.issue_type, issue_type),
        (Issue.assigned_to, assigned_to),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Issue.title.ilike(like), Issue.code.ilike(like), Issue.description.ilike(like))
        )
    now = _now()
    if overdue is True:
        stmt = stmt.where(Issue.due_at < now, Issue.status.not_in(_FINISHED))
    elif overdue is False:
        stmt = stmt.where(
            or_(Issue.due_at.is_(None), Issue.due_at >= now, Issue.status.in_(_FINISHED))
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Issue.due_at.nulls_last(), Issue.reported_at.desc(), Issue.code)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[IssueOut](
        items=[_out(i, now) for i in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/issues", response_model=IssueOut, status_code=201)
async def create_issue(
    body: IssueIn, request: Request, user: Writer, session: SessionDep
) -> IssueOut:
    await _check_refs(session, body.package_id, body.assigned_to)
    now = _now()
    due = compute_due_at(body.level, body.issue_type, now, await _holidays(session), _tz())
    if due is None:  # level 3: entered by hand
        due = body.due_at
    issue = Issue(
        code=await next_code(session, Issue, "V"),
        project_id=current_project_id(),
        package_id=body.package_id,
        issue_type=body.issue_type,
        level=body.level,
        title=body.title,
        description=body.description,
        reported_by=user.id,
        assigned_to=body.assigned_to,
        reported_at=now,
        escalated_at=now if body.level > 1 else None,
        due_at=due,
        status="open",
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(issue)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "conflict", "Mã vướng mắc bị trùng, vui lòng thử lại") from exc
    _event(session, issue, user, "created", to_level=issue.level)
    _audit(
        session,
        user,
        request,
        "create",
        issue,
        {
            "code": issue.code,
            "level": issue.level,
            "issue_type": issue.issue_type,
            "title": issue.title,
            "due_at": issue.due_at,
        },
    )
    await session.commit()
    await session.refresh(issue)
    return _out(issue)


@router.get("/issues/{issue_id}", response_model=IssueDetail)
async def read_issue(issue_id: uuid.UUID, _: Reader, session: SessionDep) -> IssueDetail:
    issue = await _issue_or_404(session, issue_id)
    events = (
        (
            await session.execute(
                select(IssueEvent)
                .where(IssueEvent.issue_id == issue.id)
                .order_by(IssueEvent.ts, IssueEvent.id)
            )
        )
        .scalars()
        .all()
    )
    detail = IssueDetail.model_validate(_out(issue))
    detail.events = [IssueEventOut.model_validate(e) for e in events]
    return detail


@router.patch("/issues/{issue_id}", response_model=IssueOut)
async def update_issue(
    issue_id: uuid.UUID, body: IssueUpdate, request: Request, user: Writer, session: SessionDep
) -> IssueOut:
    issue = await _issue_or_404(session, issue_id)
    changes = body.model_dump(exclude_unset=True)
    reason = changes.pop("due_reason", None)
    nulls = sorted(
        k for k in ("title", "issue_type", "status") if k in changes and changes[k] is None
    )
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    if "assigned_to" in changes:
        await _check_refs(session, None, changes["assigned_to"])

    tracked = (
        "title",
        "description",
        "issue_type",
        "assigned_to",
        "status",
        "due_at",
        "decided_by",
        "decision_doc_id",
    )
    before = audit.snapshot(issue, tracked)
    old_status = issue.status

    new_status = changes.get("status")
    if new_status is not None and new_status != old_status:
        if new_status not in _TRANSITIONS.get(old_status, frozenset()):
            raise AppError(
                400, "bad_request", f"Không thể chuyển từ {old_status} sang {new_status}"
            )
        if (
            new_status == "closed"
            and issue.level == 3
            and not can(user.effective_role, "risk", Level.APPROVE)
        ):
            raise AppError(403, "forbidden", "Chỉ Giám đốc QLDA được đóng vướng mắc cấp 3")
    if "due_at" in changes and changes["due_at"] != issue.due_at and not reason:
        raise AppError(
            422, "validation_error", "Cần nêu lý do khi sửa tay hạn xử lý", ["due_reason"]
        )

    for field, value in changes.items():
        setattr(issue, field, value)
    issue.updated_by = user.id
    if new_status is not None and new_status != old_status:
        if old_status in _FINISHED and new_status == "open":
            issue.resolved_at = None
            _event(session, issue, user, "reopened")
        elif new_status == "closed":
            _event(session, issue, user, "closed")
        else:
            _event(session, issue, user, "status_changed", note=f"{old_status} → {new_status}")
    if "due_at" in changes and changes["due_at"] != before["due_at"]:
        _event(session, issue, user, "due_changed", note=reason)
    if "assigned_to" in changes and changes["assigned_to"] != before["assigned_to"]:
        _event(session, issue, user, "assigned")

    delta = audit.diff(before, audit.snapshot(issue, tracked))
    if delta:
        _audit(session, user, request, "update", issue, delta)
    await session.commit()
    await session.refresh(issue)
    return _out(issue)


@router.post("/issues/{issue_id}/escalate", response_model=IssueOut)
async def escalate_issue(
    issue_id: uuid.UUID,
    request: Request,
    user: Writer,
    session: SessionDep,
    body: EscalateIn | None = None,
) -> IssueOut:
    issue = await _issue_or_404(session, issue_id)
    body = body or EscalateIn()
    if issue.status in _FINISHED:
        raise AppError(409, "conflict", "Vướng mắc đã giải quyết, không thể nâng cấp")
    if issue.level >= 3:
        raise AppError(409, "conflict", "Vướng mắc đã ở cấp cao nhất")
    old_level, now = issue.level, _now()
    issue.level += 1
    issue.status = "escalated"
    issue.escalated_at = now
    # An investor request keeps its fixed 1-day deadline; others get the deadline of the new level.
    if issue.issue_type != "investor_request":
        due = compute_due_at(issue.level, issue.issue_type, now, await _holidays(session), _tz())
        issue.due_at = due if due is not None else body.due_at
    issue.updated_by = user.id
    _event(
        session,
        issue,
        user,
        "escalated",
        from_level=old_level,
        to_level=issue.level,
        note=body.note,
    )
    _audit(
        session,
        user,
        request,
        "update",
        issue,
        {
            "level": {"before": old_level, "after": issue.level},
            "status": {"before": "open", "after": "escalated"},
            "due_at": issue.due_at,
        },
    )
    await session.commit()
    await session.refresh(issue)
    return _out(issue)


@router.post("/issues/{issue_id}/resolve", response_model=IssueOut)
async def resolve_issue(
    issue_id: uuid.UUID, body: ResolveIn, request: Request, user: Writer, session: SessionDep
) -> IssueOut:
    issue = await _issue_or_404(session, issue_id)
    if issue.status in _FINISHED:
        raise AppError(409, "conflict", "Vướng mắc đã được giải quyết")
    issue.status = "resolved"
    issue.resolution = body.resolution
    issue.decided_by = body.decided_by
    issue.decision_doc_id = body.decision_doc_id
    issue.resolved_at = _now()
    issue.updated_by = user.id
    _event(session, issue, user, "resolved", note=body.resolution)
    _audit(
        session,
        user,
        request,
        "update",
        issue,
        {"status": {"before": "open", "after": "resolved"}, "resolution": body.resolution},
    )
    await session.commit()
    await session.refresh(issue)
    return _out(issue)


# --- holidays used by the level-2 deadline ---------------------------------------------


@router.get("/admin/holidays", response_model=list[HolidayOut])
async def list_holidays(_: Admin, session: SessionDep) -> list[Holiday]:
    return list((await session.execute(select(Holiday).order_by(Holiday.day))).scalars().all())


@router.post("/admin/holidays", response_model=HolidayOut, status_code=201)
async def add_holiday(
    body: HolidayIn, request: Request, admin: Admin, session: SessionDep
) -> Holiday:
    if (await session.execute(select(Holiday.id).where(Holiday.day == body.day))).first():
        raise AppError(409, "conflict", "Ngày lễ đã tồn tại")
    holiday = Holiday(day=body.day, name=body.name, created_by=admin.id, updated_by=admin.id)
    session.add(holiday)
    await session.flush()
    audit.record(
        session,
        action="create",
        entity_type="holiday",
        entity_id=holiday.id,
        user_id=admin.id,
        changes={"day": body.day, "name": body.name},
        request=request,
    )
    await session.commit()
    await session.refresh(holiday)
    return holiday


@router.delete("/admin/holidays/{holiday_id}", status_code=204)
async def delete_holiday(
    holiday_id: uuid.UUID, request: Request, admin: Admin, session: SessionDep
) -> Response:
    holiday = await session.get(Holiday, holiday_id)
    if holiday is None:
        raise AppError(404, "not_found", "Không tìm thấy ngày lễ")
    audit.record(
        session,
        action="delete",
        entity_type="holiday",
        entity_id=holiday.id,
        user_id=admin.id,
        changes={"day": holiday.day, "name": holiday.name},
        request=request,
    )
    await session.delete(holiday)
    await session.commit()
    return Response(status_code=204)
