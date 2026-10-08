"""Global search (SPEC 4.16): packages, contracts, documents, risks and issues in one call."""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from app.core.deps import CurrentUser, ProjectCtx, SessionDep
from app.core.rbac import Level, can
from app.core.scope import current_project_id
from app.models import Contract, Document, Issue, Package, Risk
from app.schemas.search import SearchGroup, SearchHit, SearchKind, SearchOut
from app.services.documents import accessible_package_ids, visible_clause
from app.services.search import MIN_QUERY_LENGTH, escape_like, first_snippet

router = APIRouter(tags=["search"])


def _matches(query: str, *columns: InstrumentedAttribute[Any]) -> ColumnElement[bool]:
    """Accent- and case-insensitive substring match on any of the columns."""
    needle = f"%{escape_like(query)}%"
    return or_(
        *(
            func.unaccent(func.coalesce(c, "")).ilike(func.unaccent(needle), escape="\\")
            for c in columns
        )
    )


async def _page(session: SessionDep, stmt: Any, limit: int) -> tuple[int, list[Any]]:
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await session.execute(stmt.limit(limit))).all()
    return total, list(rows)


def _label(number: int | None) -> str | None:
    return f"Gói {number:02d}" if number is not None else None


@router.get("/search", response_model=SearchOut)
async def search(
    user: CurrentUser,
    _ctx: ProjectCtx,
    session: SessionDep,
    q: Annotated[str, Query(min_length=MIN_QUERY_LENGTH, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> SearchOut:
    """Hits grouped by kind with an excerpt; groups the caller may not read are left out."""
    query = q.strip()
    groups: list[SearchGroup] = []

    def add(kind: SearchKind, total: int, items: list[SearchHit]) -> None:
        if total:
            groups.append(SearchGroup(kind=kind, total=total, items=items))

    if can(user.effective_role, "package", Level.READ):
        stmt: Any = (
            select(Package)
            .where(
                Package.deleted_at.is_(None),
                Package.project_id == current_project_id(),
                _matches(
                    query,
                    Package.name,
                    Package.scope_summary,
                    Package.winning_org_text,
                    Package.etbmt_no,
                    Package.notes,
                ),
            )
            .order_by(Package.number)
        )
        total, rows = await _page(session, stmt, limit)
        add(
            "package",
            total,
            [
                SearchHit(
                    kind="package",
                    id=p.id,
                    title=f"{_label(p.number)} · {p.name}",
                    subtitle=p.winning_org_text,
                    snippet=first_snippet(
                        query, p.name, p.scope_summary, p.winning_org_text, p.etbmt_no, p.notes
                    ),
                    package_id=p.id,
                    package_number=p.number,
                )
                for (p,) in rows
            ],
        )

    if can(user.effective_role, "contract", Level.READ):
        stmt = (
            select(Contract, Package.number)
            .join(Package, Package.id == Contract.package_id)
            .where(
                Contract.deleted_at.is_(None),
                Package.project_id == current_project_id(),
                _matches(
                    query,
                    Contract.contract_no,
                    Contract.investor_signer,
                    Contract.payment_terms_text,
                    Contract.data_quality_note,
                    Contract.advance_recovery_note,
                ),
            )
            .order_by(Package.number, Contract.contract_no)
        )
        total, rows = await _page(session, stmt, limit)
        add(
            "contract",
            total,
            [
                SearchHit(
                    kind="contract",
                    id=c.id,
                    title=f"Hợp đồng {c.contract_no}",
                    subtitle=_label(number),
                    snippet=first_snippet(
                        query,
                        c.contract_no,
                        c.investor_signer,
                        c.payment_terms_text,
                        c.data_quality_note,
                        c.advance_recovery_note,
                    ),
                    package_id=c.package_id,
                    package_number=number,
                )
                for c, number in rows
            ],
        )

    if can(user.effective_role, "document", Level.READ):
        access_ids = await accessible_package_ids(session, user)
        vector = func.plainto_tsquery("simple", func.unaccent(query))
        stmt = (
            select(Document, Package.number)
            .outerjoin(Package, Package.id == Document.package_id)
            .where(
                Document.deleted_at.is_(None),
                Document.project_id == current_project_id(),
                Document.is_current.is_(True),
                visible_clause(user, access_ids),
                or_(
                    _matches(
                        query, Document.title, Document.doc_no, Document.notes, Document.file_name
                    ),
                    Document.search_vector.op("@@")(vector),
                ),
            )
            .order_by(
                func.ts_rank(Document.search_vector, vector).desc(), Document.created_at.desc()
            )
        )
        total, rows = await _page(session, stmt, limit)
        add(
            "document",
            total,
            [
                SearchHit(
                    kind="document",
                    id=d.id,
                    title=d.title,
                    subtitle=" · ".join(x for x in (d.doc_no, _label(number)) if x) or None,
                    snippet=first_snippet(query, d.title, d.doc_no, d.notes, d.text_content),
                    package_id=d.package_id,
                    package_number=number,
                )
                for d, number in rows
            ],
        )

    if can(user.effective_role, "risk", Level.READ):
        risk_stmt = (
            select(Risk, Package.number)
            .outerjoin(Package, Package.id == Risk.package_id)
            .where(
                Risk.project_id == current_project_id(),
                _matches(
                    query,
                    Risk.code,
                    Risk.title,
                    Risk.description,
                    Risk.mitigation,
                    Risk.contingency,
                ),
            )
            .order_by(Risk.code)
        )
        total, rows = await _page(session, risk_stmt, limit)
        add(
            "risk",
            total,
            [
                SearchHit(
                    kind="risk",
                    id=r.id,
                    title=f"{r.code} · {r.title}",
                    subtitle=_label(number),
                    snippet=first_snippet(query, r.title, r.description, r.mitigation),
                    package_id=r.package_id,
                    package_number=number,
                )
                for r, number in rows
            ],
        )
        issue_stmt = (
            select(Issue, Package.number)
            .outerjoin(Package, Package.id == Issue.package_id)
            .where(
                Issue.project_id == current_project_id(),
                _matches(query, Issue.code, Issue.title, Issue.description, Issue.resolution),
            )
            .order_by(Issue.code)
        )
        total, rows = await _page(session, issue_stmt, limit)
        add(
            "issue",
            total,
            [
                SearchHit(
                    kind="issue",
                    id=i.id,
                    title=f"{i.code} · {i.title}",
                    subtitle=_label(number),
                    snippet=first_snippet(query, i.title, i.description, i.resolution),
                    package_id=i.package_id,
                    package_number=number,
                )
                for i, number in rows
            ],
        )

    return SearchOut(query=query, groups=groups)
