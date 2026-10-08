import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import Integer, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import ProjectDep, SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level, can
from app.core.scope import current_project_id
from app.models import Package, Risk, User
from app.schemas.common import Page, PaginationDep
from app.schemas.risk import MatrixCell, MatrixOut, RiskIn, RiskOut, RiskUpdate
from app.services import audit
from app.services.risk_rules import (
    matrix_counts,
    risk_level,
    risk_needs_review,
    risk_score,
)

router = APIRouter(tags=["risks"])

Reader = Annotated[User, Depends(require("risk", Level.READ))]
Writer = Annotated[User, Depends(require("risk", Level.WRITE))]

_TRACKED = (
    "package_id",
    "title",
    "description",
    "category",
    "probability",
    "impact",
    "score",
    "owner_id",
    "mitigation",
    "contingency",
    "group_name",
    "owner_text",
    "note",
    "status",
    "due_date",
)
_NON_NULL = frozenset({"title", "category", "probability", "impact", "status"})
_LEVEL_RANGES = {"low": (1, 5), "medium": (6, 12), "high": (13, 25)}


async def next_code(session: AsyncSession, model: Any, prefix: str) -> str:
    """Sequential human codes (R-001, V-014, ...); an advisory lock serialises creators."""
    project_id = current_project_id()
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"code:{project_id}:{prefix}"}
    )
    last = (
        await session.execute(
            select(
                func.coalesce(func.max(cast(func.substr(model.code, len(prefix) + 2), Integer)), 0)
            ).where(model.project_id == project_id)
        )
    ).scalar_one()
    return f"{prefix}-{last + 1:03d}"


def _out(risk: Risk, now: datetime | None = None) -> RiskOut:
    out = RiskOut.model_validate(risk)
    out.level = risk_level(risk.score)
    out.needs_review = risk_needs_review(
        risk.status, risk.created_at, risk.last_reviewed_at, now or datetime.now(UTC)
    )
    return out


async def _risk_or_404(session: AsyncSession, risk_id: uuid.UUID) -> Risk:
    risk = await session.get(Risk, risk_id)
    if risk is None or risk.project_id != current_project_id():
        raise AppError(404, "not_found", "Không tìm thấy rủi ro")
    return risk


async def _check_refs(session: AsyncSession, data: dict[str, Any]) -> None:
    if data.get("package_id") is not None:
        package = await session.get(Package, data["package_id"])
        if package is None or package.project_id != current_project_id():
            raise AppError(422, "validation_error", "Gói thầu không tồn tại", ["package_id"])
    if data.get("owner_id") is not None:
        owner = await session.get(User, data["owner_id"])
        if owner is None or not owner.is_active:
            raise AppError(422, "validation_error", "Người phụ trách không hợp lệ", ["owner_id"])


@router.get("/risks", response_model=Page[RiskOut])
async def list_risks(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    package_id: uuid.UUID | None = None,
    status: str | None = None,
    category: str | None = None,
    owner_id: uuid.UUID | None = None,
    level: Annotated[str | None, Query(pattern="^(low|medium|high)$")] = None,
    probability: Annotated[int | None, Query(ge=1, le=5)] = None,
    impact: Annotated[int | None, Query(ge=1, le=5)] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[RiskOut]:
    stmt = select(Risk).where(Risk.project_id == current_project_id())
    for column, value in (
        (Risk.package_id, package_id),
        (Risk.status, status),
        (Risk.category, category),
        (Risk.owner_id, owner_id),
        (Risk.probability, probability),
        (Risk.impact, impact),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if level:
        low, high = _LEVEL_RANGES[level]
        stmt = stmt.where(Risk.score.between(low, high))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Risk.title.ilike(like), Risk.code.ilike(like), Risk.description.ilike(like))
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(Risk.score.desc(), Risk.code)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    now = datetime.now(UTC)
    return Page[RiskOut](
        items=[_out(r, now) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.get("/risks/matrix", response_model=MatrixOut)
async def risk_matrix(
    _: Reader,
    session: SessionDep,
    package_id: uuid.UUID | None = None,
    include_closed: bool = False,
) -> MatrixOut:
    """5x5 heat map of risks; closed ones are left out unless asked for."""
    stmt = select(Risk.id, Risk.probability, Risk.impact).where(
        Risk.project_id == current_project_id()
    )
    if not include_closed:
        stmt = stmt.where(Risk.status != "closed")
    if package_id:
        stmt = stmt.where(Risk.package_id == package_id)
    rows = (await session.execute(stmt)).all()
    counts = matrix_counts((p, i) for _id, p, i in rows)
    ids: dict[tuple[int, int], list[uuid.UUID]] = {}
    for rid, p, i in rows:
        ids.setdefault((p, i), []).append(rid)
    cells = [
        MatrixCell(probability=p, impact=i, count=n, risk_ids=ids.get((p, i), []))
        for (p, i), n in sorted(counts.items(), reverse=True)
    ]
    return MatrixOut(cells=cells, total=len(rows))


@router.post("/risks", response_model=RiskOut, status_code=201)
async def create_risk(
    body: RiskIn, request: Request, user: Writer, session: SessionDep, project: ProjectDep
) -> RiskOut:
    data = body.model_dump(exclude_unset=True)
    await _check_refs(session, data)
    risk = Risk(
        code=await next_code(session, Risk, "R"),
        project_id=project.id,
        score=risk_score(body.probability, body.impact),
        created_by=user.id,
        updated_by=user.id,
        **data,
    )
    session.add(risk)
    await session.flush()
    audit.record(
        session,
        action="create",
        entity_type="risk",
        entity_id=risk.id,
        user_id=user.id,
        changes=audit.snapshot(risk, ("code", *_TRACKED)),
        request=request,
    )
    await session.commit()
    await session.refresh(risk)
    return _out(risk)


@router.get("/risks/{risk_id}", response_model=RiskOut)
async def read_risk(risk_id: uuid.UUID, _: Reader, session: SessionDep) -> RiskOut:
    return _out(await _risk_or_404(session, risk_id))


@router.patch("/risks/{risk_id}", response_model=RiskOut)
async def update_risk(
    risk_id: uuid.UUID, body: RiskUpdate, request: Request, user: Writer, session: SessionDep
) -> RiskOut:
    risk = await _risk_or_404(session, risk_id)
    changes = body.model_dump(exclude_unset=True)
    nulls = sorted(k for k, v in changes.items() if v is None and k in _NON_NULL)
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    await _check_refs(session, changes)
    # Only the director closes (or reopens) a risk (SPEC 4.8, matrix "A").
    new_status = changes.get("status")
    closing_or_reopening = (
        new_status is not None
        and new_status != risk.status
        and "closed" in {new_status, risk.status}
    )
    if closing_or_reopening and not can(user.effective_role, "risk", Level.APPROVE):
        raise AppError(403, "forbidden", "Chỉ Giám đốc QLDA được đóng hoặc mở lại rủi ro")
    before = audit.snapshot(risk, _TRACKED)
    for field, value in changes.items():
        setattr(risk, field, value)
    risk.score = risk_score(risk.probability, risk.impact)
    risk.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(risk, _TRACKED))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="risk",
            entity_id=risk.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    await session.refresh(risk)
    return _out(risk)


@router.post("/risks/{risk_id}/review", response_model=RiskOut)
async def review_risk(
    risk_id: uuid.UUID, request: Request, user: Writer, session: SessionDep
) -> RiskOut:
    """Record that someone re-assessed the risk; resets the 14-day reminder."""
    risk = await _risk_or_404(session, risk_id)
    risk.last_reviewed_at = datetime.now(UTC)
    risk.updated_by = user.id
    audit.record(
        session,
        action="update",
        entity_type="risk",
        entity_id=risk.id,
        user_id=user.id,
        changes={"last_reviewed_at": risk.last_reviewed_at},
        request=request,
    )
    await session.commit()
    await session.refresh(risk)
    return _out(risk)
