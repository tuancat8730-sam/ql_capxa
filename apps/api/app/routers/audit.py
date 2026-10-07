import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.deps import SessionDep, require
from app.core.rbac import Level
from app.models import AuditLog, User
from app.schemas.audit import AuditFacets, AuditLogOut, AuditUser
from app.schemas.common import Page, PaginationDep

router = APIRouter(prefix="/audit-log", tags=["audit"])

Reader = Annotated[User, Depends(require("audit_log", Level.READ))]


@router.get("/facets", response_model=AuditFacets)
async def audit_facets(_: Reader, session: SessionDep) -> AuditFacets:
    actions = await session.execute(select(AuditLog.action).distinct().order_by(AuditLog.action))
    kinds = await session.execute(
        select(AuditLog.entity_type).distinct().order_by(AuditLog.entity_type)
    )
    users = await session.execute(
        select(User.id, User.full_name)
        .where(User.id.in_(select(AuditLog.user_id).distinct()))
        .order_by(User.full_name)
    )
    return AuditFacets(
        actions=list(actions.scalars().all()),
        entity_types=list(kinds.scalars().all()),
        users=[AuditUser(id=i, name=n) for i, n in users.all()],
    )


@router.get("", response_model=Page[AuditLogOut])
async def list_audit_log(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: uuid.UUID | None = None,
    ts_from: datetime | None = None,
    ts_to: datetime | None = None,
) -> Page[AuditLogOut]:
    stmt = select(AuditLog, User.full_name).outerjoin(User, User.id == AuditLog.user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if ts_from:
        stmt = stmt.where(AuditLog.ts >= ts_from)
    if ts_to:
        stmt = stmt.where(AuditLog.ts <= ts_to)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await session.execute(
            stmt.order_by(AuditLog.ts.desc(), AuditLog.id)
            .offset(pagination.offset)
            .limit(pagination.page_size)
        )
    ).all()
    items = []
    for row, name in rows:
        out = AuditLogOut.model_validate(row)
        out.user_name = name
        items.append(out)
    return Page[AuditLogOut](
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
