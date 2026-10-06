import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.core.deps import SessionDep, require
from app.core.rbac import Level
from app.models import AuditLog, User
from app.schemas.audit import AuditLogOut
from app.schemas.common import Page, PaginationDep

router = APIRouter(prefix="/audit-log", tags=["audit"])

Reader = Annotated[User, Depends(require("audit_log", Level.READ))]


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
    stmt = select(AuditLog)
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
        (
            await session.execute(
                stmt.order_by(AuditLog.ts.desc(), AuditLog.id)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[AuditLogOut](
        items=[AuditLogOut.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )
