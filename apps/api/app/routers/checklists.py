import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import ChecklistItem, Document, User
from app.routers.packages import package_or_404
from app.schemas.document import ChecklistItemOut, ChecklistItemUpdate, ChecklistOut
from app.services import audit
from app.services.documents import accessible_package_ids, can_view, instantiate_checklist
from app.services.finance import today_local

router = APIRouter(tags=["checklists"])

Reader = Annotated[User, Depends(require("document", Level.READ))]
Writer = Annotated[User, Depends(require("document", Level.WRITE))]

_STAGE_ORDER = {
    "S1_START": 1,
    "S2_SELECTION": 2,
    "S3_EXECUTION": 3,
    "S4_ACCEPTANCE": 4,
    "S5_PAYMENT_SETTLEMENT": 5,
}


async def _build(session: AsyncSession, user: User, package_id: uuid.UUID) -> ChecklistOut:
    rows = (
        (await session.execute(select(ChecklistItem).where(ChecklistItem.package_id == package_id)))
        .scalars()
        .all()
    )
    rows = sorted(rows, key=lambda r: (_STAGE_ORDER.get(r.stage_code, 9), r.sort_order))
    access_ids = await accessible_package_ids(session, user)
    docs = {
        d.id: d
        for d in (
            await session.execute(
                select(Document).where(
                    Document.id.in_([r.document_id for r in rows if r.document_id])
                )
            )
        )
        .scalars()
        .all()
    }
    today = today_local()
    items: list[ChecklistItemOut] = []
    for r in rows:
        out = ChecklistItemOut.model_validate(r)
        doc = docs.get(r.document_id) if r.document_id else None
        if doc is not None:
            if can_view(user, doc, access_ids):
                out.document_title = doc.title
            else:
                out.document_restricted = True
        out.overdue = (
            r.required and r.status == "missing" and r.due_date is not None and r.due_date < today
        )
        items.append(out)
    counted = [i for i in items if i.required and i.status != "not_applicable"]
    done = sum(1 for i in counted if i.status == "received")
    pct = round(done / len(counted) * 100, 1) if counted else 100.0
    return ChecklistOut(
        items=items, required_total=len(counted), required_done=done, completion_pct=pct
    )


@router.get("/packages/{package_id}/checklist", response_model=ChecklistOut)
async def read_checklist(package_id: uuid.UUID, user: Reader, session: SessionDep) -> ChecklistOut:
    await package_or_404(session, package_id)
    return await _build(session, user, package_id)


@router.post("/packages/{package_id}/checklist/instantiate", response_model=ChecklistOut)
async def instantiate(
    package_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> ChecklistOut:
    package = await package_or_404(session, package_id)
    created = await instantiate_checklist(session, package)
    if created:
        audit.record(
            session,
            action="create",
            entity_type="checklist",
            entity_id=package.id,
            user_id=user.id,
            changes={"items_created": created},
            request=request,
        )
    await session.commit()
    return await _build(session, user, package_id)


@router.patch("/checklist-items/{item_id}", response_model=ChecklistItemOut)
async def update_item(
    item_id: uuid.UUID,
    body: ChecklistItemUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> ChecklistItemOut:
    item = await session.get(ChecklistItem, item_id)
    if item is None:
        raise AppError(404, "not_found", "Không tìm thấy hạng mục")
    await package_or_404(session, item.package_id)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("status") is None and "status" in changes:
        raise AppError(422, "validation_error", "Trạng thái không được để trống", ["status"])

    if "document_id" in changes and changes["document_id"] is not None:
        access_ids = await accessible_package_ids(session, user)
        doc = await session.get(Document, changes["document_id"])
        if (
            doc is None
            or doc.deleted_at is not None
            or doc.package_id != item.package_id
            or not can_view(user, doc, access_ids)
        ):
            raise AppError(422, "validation_error", "Tài liệu không thuộc gói này", ["document_id"])
        changes["status"] = "received"
    if changes.get("status") in {"missing", "not_applicable"}:
        changes["document_id"] = None
    if (
        changes.get("status") == "received"
        and item.document_id is None
        and not changes.get("document_id")
    ):
        raise AppError(
            422, "validation_error", "Cần chọn tài liệu để đánh dấu đã nhận", ["document_id"]
        )

    before = audit.snapshot(item, changes)
    for field, value in changes.items():
        setattr(item, field, value)
    item.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(item, changes))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="checklist_item",
            entity_id=item.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    checklist = await _build(session, user, item.package_id)
    return next(i for i in checklist.items if i.id == item.id)
