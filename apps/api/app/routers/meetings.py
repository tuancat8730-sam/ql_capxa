import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import (
    ActionItem,
    ChangeRequest,
    ContractAmendment,
    Meeting,
    Organization,
    Package,
    User,
)
from app.routers.project import get_single_project
from app.routers.risks import next_code
from app.schemas.common import Page, PaginationDep
from app.schemas.risk import (
    ActionIn,
    ActionOut,
    ActionUpdate,
    ChangeIn,
    ChangeOut,
    ChangeUpdate,
    DecideIn,
    MeetingIn,
    MeetingOut,
    MeetingUpdate,
)
from app.services import audit
from app.services.finance import today_local

router = APIRouter(tags=["meetings"])

Reader = Annotated[User, Depends(require("meeting", Level.READ))]
Writer = Annotated[User, Depends(require("meeting", Level.WRITE))]
Approver = Annotated[User, Depends(require("meeting", Level.APPROVE))]


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


async def _check_package(session: AsyncSession, package_id: uuid.UUID | None) -> None:
    if package_id is not None and await session.get(Package, package_id) is None:
        raise AppError(422, "validation_error", "Gói thầu không tồn tại", ["package_id"])


async def _check_owner(session: AsyncSession, owner_id: uuid.UUID | None) -> None:
    if owner_id is not None:
        owner = await session.get(User, owner_id)
        if owner is None or not owner.is_active:
            raise AppError(422, "validation_error", "Người phụ trách không hợp lệ", ["owner_id"])


# --- meetings ---------------------------------------------------------------------------------


def _meeting_out(meeting: Meeting, open_actions: int = 0) -> MeetingOut:
    out = MeetingOut.model_validate(meeting)
    out.open_actions = open_actions
    return out


async def _open_actions(
    session: AsyncSession, meeting_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not meeting_ids:
        return {}
    rows = (
        await session.execute(
            select(ActionItem.meeting_id, func.count())
            .where(ActionItem.meeting_id.in_(meeting_ids), ActionItem.status == "open")
            .group_by(ActionItem.meeting_id)
        )
    ).all()
    return {mid: n for mid, n in rows if mid is not None}


async def _meeting_or_404(session: AsyncSession, meeting_id: uuid.UUID) -> Meeting:
    meeting = await session.get(Meeting, meeting_id)
    if meeting is None:
        raise AppError(404, "not_found", "Không tìm thấy cuộc họp")
    return meeting


@router.get("/meetings", response_model=Page[MeetingOut])
async def list_meetings(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    package_id: uuid.UUID | None = None,
    meeting_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[MeetingOut]:
    stmt = select(Meeting)
    if package_id:
        stmt = stmt.where(Meeting.package_id == package_id)
    if meeting_type:
        stmt = stmt.where(Meeting.meeting_type == meeting_type)
    if date_from:
        stmt = stmt.where(Meeting.meeting_date >= date_from)
    if date_to:
        stmt = stmt.where(Meeting.meeting_date <= date_to)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Meeting.meeting_date.desc(), Meeting.created_at.desc())
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    counts = await _open_actions(session, [m.id for m in rows])
    return Page[MeetingOut](
        items=[_meeting_out(m, counts.get(m.id, 0)) for m in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/meetings", response_model=MeetingOut, status_code=201)
async def create_meeting(
    body: MeetingIn, request: Request, user: Writer, session: SessionDep
) -> MeetingOut:
    await _check_package(session, body.package_id)
    project = await get_single_project(session)
    data = body.model_dump(exclude_unset=True, mode="json")
    meeting = Meeting(
        project_id=project.id,
        created_by=user.id,
        updated_by=user.id,
        **{**data, "meeting_date": body.meeting_date},
    )
    session.add(meeting)
    await session.flush()
    _audit(
        session,
        user,
        request,
        "create",
        "meeting",
        meeting.id,
        {"meeting_type": body.meeting_type, "meeting_date": body.meeting_date},
    )
    await session.commit()
    await session.refresh(meeting)
    return _meeting_out(meeting)


@router.get("/meetings/{meeting_id}", response_model=MeetingOut)
async def read_meeting(meeting_id: uuid.UUID, _: Reader, session: SessionDep) -> MeetingOut:
    meeting = await _meeting_or_404(session, meeting_id)
    return _meeting_out(meeting, (await _open_actions(session, [meeting.id])).get(meeting.id, 0))


@router.patch("/meetings/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: uuid.UUID, body: MeetingUpdate, request: Request, user: Writer, session: SessionDep
) -> MeetingOut:
    meeting = await _meeting_or_404(session, meeting_id)
    changes = body.model_dump(exclude_unset=True, mode="json")
    if "meeting_date" in changes:
        if changes["meeting_date"] is None:
            raise AppError(
                422, "validation_error", "Ngày họp không được để trống", ["meeting_date"]
            )
        changes["meeting_date"] = body.meeting_date
    if changes.get("meeting_type", "x") is None:
        raise AppError(
            422, "validation_error", "Loại cuộc họp không được để trống", ["meeting_type"]
        )
    if "attendees" in changes and changes["attendees"] is None:
        changes["attendees"] = []
    await _check_package(session, changes.get("package_id"))
    before = audit.snapshot(meeting, changes)
    for field, value in changes.items():
        setattr(meeting, field, value)
    meeting.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(meeting, changes))
    if delta:
        _audit(session, user, request, "update", "meeting", meeting.id, delta)
    await session.commit()
    await session.refresh(meeting)
    return _meeting_out(meeting, (await _open_actions(session, [meeting.id])).get(meeting.id, 0))


# --- action items -----------------------------------------------------------------------------


def _action_out(item: ActionItem, today: date) -> ActionOut:
    out = ActionOut.model_validate(item)
    out.overdue = item.status == "open" and item.due_date is not None and item.due_date < today
    return out


async def _action_or_404(session: AsyncSession, action_id: uuid.UUID) -> ActionItem:
    item = await session.get(ActionItem, action_id)
    if item is None:
        raise AppError(404, "not_found", "Không tìm thấy đầu việc")
    return item


@router.get("/meetings/{meeting_id}/action-items", response_model=list[ActionOut])
async def list_meeting_actions(
    meeting_id: uuid.UUID, _: Reader, session: SessionDep
) -> list[ActionOut]:
    await _meeting_or_404(session, meeting_id)
    rows = (
        (
            await session.execute(
                select(ActionItem)
                .where(ActionItem.meeting_id == meeting_id)
                .order_by(ActionItem.due_date.nulls_last(), ActionItem.created_at)
            )
        )
        .scalars()
        .all()
    )
    today = today_local()
    return [_action_out(i, today) for i in rows]


@router.post("/meetings/{meeting_id}/action-items", response_model=ActionOut, status_code=201)
async def create_action(
    meeting_id: uuid.UUID, body: ActionIn, request: Request, user: Writer, session: SessionDep
) -> ActionOut:
    meeting = await _meeting_or_404(session, meeting_id)
    await _check_owner(session, body.owner_id)
    data = body.model_dump(exclude_unset=True)
    data.setdefault("package_id", meeting.package_id)
    await _check_package(session, data.get("package_id"))
    item = ActionItem(meeting_id=meeting_id, created_by=user.id, updated_by=user.id, **data)
    session.add(item)
    await session.flush()
    _audit(
        session, user, request, "create", "action_item", item.id, {"meeting_id": meeting_id, **data}
    )
    await session.commit()
    await session.refresh(item)
    return _action_out(item, today_local())


@router.get("/action-items", response_model=Page[ActionOut])
async def list_actions(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    status: str | None = None,
    owner_id: uuid.UUID | None = None,
    package_id: uuid.UUID | None = None,
    overdue: Annotated[bool | None, Query()] = None,
) -> Page[ActionOut]:
    """All action items, e.g. the overdue ones for the dashboard (SPEC 4.11)."""
    today = today_local()
    stmt = select(ActionItem)
    if status:
        stmt = stmt.where(ActionItem.status == status)
    if owner_id:
        stmt = stmt.where(ActionItem.owner_id == owner_id)
    if package_id:
        stmt = stmt.where(ActionItem.package_id == package_id)
    if overdue:
        stmt = stmt.where(ActionItem.status == "open", ActionItem.due_date < today)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(ActionItem.due_date.nulls_last(), ActionItem.created_at)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[ActionOut](
        items=[_action_out(i, today) for i in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.patch("/action-items/{action_id}", response_model=ActionOut)
async def update_action(
    action_id: uuid.UUID, body: ActionUpdate, request: Request, user: Writer, session: SessionDep
) -> ActionOut:
    item = await _action_or_404(session, action_id)
    changes = body.model_dump(exclude_unset=True)
    nulls = [k for k in ("title", "status") if k in changes and changes[k] is None]
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    await _check_owner(session, changes.get("owner_id"))
    await _check_package(session, changes.get("package_id"))
    before = audit.snapshot(item, changes)
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(item, changes))
    if delta:
        _audit(session, user, request, "update", "action_item", item.id, delta)
    await session.commit()
    await session.refresh(item)
    return _action_out(item, today_local())


@router.delete("/action-items/{action_id}", status_code=204)
async def delete_action(
    action_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> Response:
    item = await _action_or_404(session, action_id)
    _audit(session, user, request, "delete", "action_item", item.id, {"title": item.title})
    await session.delete(item)
    await session.commit()
    return Response(status_code=204)


# --- change requests --------------------------------------------------------------------------


async def _change_or_404(session: AsyncSession, change_id: uuid.UUID) -> ChangeRequest:
    change = await session.get(ChangeRequest, change_id)
    if change is None:
        raise AppError(404, "not_found", "Không tìm thấy yêu cầu thay đổi")
    return change


async def _check_change_refs(
    session: AsyncSession, data: dict[str, Any], package_id: uuid.UUID | None
) -> None:
    if (
        data.get("proposed_by_org_id") is not None
        and await session.get(Organization, data["proposed_by_org_id"]) is None
    ):
        raise AppError(422, "validation_error", "Tổ chức không tồn tại", ["proposed_by_org_id"])
    if data.get("amendment_id") is not None:
        amendment = await session.get(ContractAmendment, data["amendment_id"])
        if amendment is None:
            raise AppError(422, "validation_error", "Phụ lục không tồn tại", ["amendment_id"])
    if package_id is not None:
        await _check_package(session, package_id)


@router.get("/change-requests", response_model=Page[ChangeOut])
async def list_changes(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    package_id: uuid.UUID | None = None,
    status: str | None = None,
    change_type: str | None = None,
) -> Page[ChangeOut]:
    stmt = select(ChangeRequest)
    if package_id:
        stmt = stmt.where(ChangeRequest.package_id == package_id)
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
    if change_type:
        stmt = stmt.where(ChangeRequest.change_type == change_type)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(ChangeRequest.created_at.desc(), ChangeRequest.code)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[ChangeOut](
        items=[ChangeOut.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/change-requests", response_model=ChangeOut, status_code=201)
async def create_change(
    body: ChangeIn, request: Request, user: Writer, session: SessionDep
) -> ChangeRequest:
    data = body.model_dump(exclude_unset=True)
    await _check_change_refs(session, data, body.package_id)
    change = ChangeRequest(
        code=await next_code(session, ChangeRequest, "C"),
        created_by=user.id,
        updated_by=user.id,
        **data,
    )
    session.add(change)
    await session.flush()
    _audit(
        session,
        user,
        request,
        "create",
        "change_request",
        change.id,
        {"code": change.code, "change_type": change.change_type, "package_id": change.package_id},
    )
    await session.commit()
    await session.refresh(change)
    return change


@router.get("/change-requests/{change_id}", response_model=ChangeOut)
async def read_change(change_id: uuid.UUID, _: Reader, session: SessionDep) -> ChangeRequest:
    return await _change_or_404(session, change_id)


_CHANGE_MOVES: dict[str, frozenset[str]] = {
    "proposed": frozenset({"reviewing"}),
    "reviewing": frozenset({"proposed"}),
    "approved": frozenset({"appendix_signed"}),
    "rejected": frozenset(),
    "appendix_signed": frozenset(),
}


@router.patch("/change-requests/{change_id}", response_model=ChangeOut)
async def update_change(
    change_id: uuid.UUID, body: ChangeUpdate, request: Request, user: Writer, session: SessionDep
) -> ChangeRequest:
    change = await _change_or_404(session, change_id)
    changes = body.model_dump(exclude_unset=True)
    nulls = [
        k for k in ("change_type", "description", "status") if k in changes and changes[k] is None
    ]
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    await _check_change_refs(session, changes, None)
    new_status = changes.get("status")
    if (
        new_status is not None
        and new_status != change.status
        and new_status not in _CHANGE_MOVES[change.status]
    ):
        raise AppError(400, "bad_request", f"Không thể chuyển từ {change.status} sang {new_status}")
    before = audit.snapshot(change, changes)
    for field, value in changes.items():
        setattr(change, field, value)
    change.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(change, changes))
    if delta:
        _audit(session, user, request, "update", "change_request", change.id, delta)
    await session.commit()
    await session.refresh(change)
    return change


@router.post("/change-requests/{change_id}/decide", response_model=ChangeOut)
async def decide_change(
    change_id: uuid.UUID, body: DecideIn, request: Request, user: Approver, session: SessionDep
) -> ChangeRequest:
    """Approve or reject (director only, matrix "A"); only an undecided request can be decided."""
    change = await _change_or_404(session, change_id)
    if change.status not in {"proposed", "reviewing"}:
        raise AppError(409, "conflict", "Yêu cầu đã được quyết định")
    before = {"status": change.status}
    change.status = body.decision
    change.decided_at = datetime.now(UTC)
    change.decided_by = user.id
    change.decision_note = body.note
    change.updated_by = user.id
    _audit(
        session,
        user,
        request,
        "update",
        "change_request",
        change.id,
        audit.diff(before, {"status": change.status}) | {"decision_note": body.note},
    )
    await session.commit()
    await session.refresh(change)
    return change
