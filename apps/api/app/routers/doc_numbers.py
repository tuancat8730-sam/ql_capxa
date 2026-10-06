"""Outgoing document numbers (SPEC 4.15): `[seq]/[kind]-QLDA-SGM`, sequential per kind and year."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select, text

from app.core.deps import SessionDep, require
from app.core.rbac import Level
from app.models import OutgoingDocNumber, User
from app.schemas.common import Page, PaginationDep
from app.schemas.doc_number import DocKind, DocNumberIn, DocNumberOut
from app.services import audit
from app.services.finance import today_local
from app.services.search import escape_like

router = APIRouter(prefix="/outgoing-doc-numbers", tags=["doc-numbers"])

Reader = Annotated[User, Depends(require("doc_number", Level.READ))]
Writer = Annotated[User, Depends(require("doc_number", Level.WRITE))]

SUFFIX = "QLDA-SGM"


def format_doc_no(seq: int, kind: str) -> str:
    return f"{seq:03d}/{kind}-{SUFFIX}"


@router.get("", response_model=Page[DocNumberOut])
async def list_numbers(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    doc_kind: DocKind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[DocNumberOut]:
    stmt = select(OutgoingDocNumber)
    if year is not None:
        stmt = stmt.where(OutgoingDocNumber.year == year)
    if doc_kind is not None:
        stmt = stmt.where(OutgoingDocNumber.doc_kind == doc_kind)
    if q and q.strip():
        like = f"%{escape_like(q.strip())}%"
        stmt = stmt.where(
            or_(
                func.unaccent(OutgoingDocNumber.subject).ilike(func.unaccent(like), escape="\\"),
                OutgoingDocNumber.doc_no.ilike(like, escape="\\"),
            )
        )
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(
                    OutgoingDocNumber.year.desc(),
                    OutgoingDocNumber.doc_kind,
                    OutgoingDocNumber.seq.desc(),
                )
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[DocNumberOut](
        items=[DocNumberOut.model_validate(r) for r in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("", response_model=DocNumberOut, status_code=201)
async def issue_number(
    body: DocNumberIn, request: Request, user: Writer, session: SessionDep
) -> DocNumberOut:
    """Take the next number for the kind and year; an advisory lock keeps concurrent users apart."""
    issued = body.issued_date or today_local()
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"doc_no:{issued.year}:{body.doc_kind}"},
    )
    last = (
        await session.execute(
            select(func.coalesce(func.max(OutgoingDocNumber.seq), 0)).where(
                OutgoingDocNumber.year == issued.year,
                OutgoingDocNumber.doc_kind == body.doc_kind,
            )
        )
    ).scalar_one()
    row = OutgoingDocNumber(
        year=issued.year,
        doc_kind=body.doc_kind,
        seq=last + 1,
        doc_no=format_doc_no(last + 1, body.doc_kind),
        subject=body.subject,
        issued_date=issued,
        created_by=user.id,
        updated_by=user.id,
        created_by_name=user.full_name,
    )
    session.add(row)
    await session.flush()
    audit.record(
        session,
        action="create",
        entity_type="outgoing_doc_number",
        entity_id=row.id,
        user_id=user.id,
        changes=audit.snapshot(row, ("doc_no", "subject", "issued_date")),
        request=request,
    )
    await session.commit()
    await session.refresh(row)
    return DocNumberOut.model_validate(row)
