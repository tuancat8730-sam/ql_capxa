import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import Contract, Package, User
from app.routers.project import _project_out, get_single_project
from app.schemas.common import Page, PaginationDep
from app.schemas.contract import ContractOut
from app.schemas.project import PackageListItem, PackageOut, PackageUpdate, ProjectOut
from app.services import audit
from app.services.contracts import contract_out
from app.services.documents import checklist_completion

router = APIRouter(prefix="/packages", tags=["packages"])

Reader = Annotated[User, Depends(require("package", Level.READ))]
Writer = Annotated[User, Depends(require("package", Level.WRITE))]

_NON_NULLABLE = frozenset({"name", "package_type", "current_stage", "status"})
_TRACKED = tuple(PackageUpdate.model_fields)


class PackageOverview(BaseModel):
    package: PackageOut
    project: ProjectOut
    contracts: list[ContractOut]
    needs_review: bool


async def package_or_404(session: AsyncSession, package_id: uuid.UUID) -> Package:
    package = await session.get(Package, package_id)
    if package is None or package.deleted_at is not None:
        raise AppError(404, "not_found", "Không tìm thấy gói thầu")
    return package


async def _contracts_of(session: AsyncSession, package_id: uuid.UUID) -> list[Contract]:
    return list(
        (
            await session.execute(
                select(Contract)
                .where(Contract.package_id == package_id, Contract.deleted_at.is_(None))
                .order_by(Contract.signed_date.nulls_last(), Contract.created_at)
            )
        )
        .scalars()
        .all()
    )


@router.get("", response_model=Page[PackageListItem])
async def list_packages(
    _: Reader,
    session: SessionDep,
    pagination: PaginationDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    status: str | None = None,
    health: str | None = None,
) -> Page[PackageListItem]:
    stmt = select(Package).where(Package.deleted_at.is_(None))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Package.name.ilike(like), Package.winning_org_text.ilike(like)))
    if status:
        stmt = stmt.where(Package.status == status)
    if health:
        stmt = stmt.where(Package.health == health)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    packages = (
        (
            await session.execute(
                stmt.order_by(Package.number).offset(pagination.offset).limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    items: list[PackageListItem] = []
    for package in packages:
        item = PackageListItem.model_validate(package)
        contracts = await _contracts_of(session, package.id)
        if contracts:
            detail = await contract_out(session, contracts[0])
            item.contract_no = detail.contract_no
            item.contract_value = detail.value
            end = detail.extended_end_date or detail.planned_end_date
            item.contract_end_date = end.isoformat() if end else None
            item.needs_review = any(c.needs_review for c in [detail])
        item.checklist_pct = await checklist_completion(session, package.id)
        items.append(item)
    return Page[PackageListItem](
        items=items, total=total, page=pagination.page, page_size=pagination.page_size
    )


@router.get("/{package_id}", response_model=PackageOut)
async def read_package(package_id: uuid.UUID, _: Reader, session: SessionDep) -> Package:
    return await package_or_404(session, package_id)


@router.patch("/{package_id}", response_model=PackageOut)
async def update_package(
    package_id: uuid.UUID,
    body: PackageUpdate,
    request: Request,
    user: Writer,
    session: SessionDep,
) -> Package:
    package = await package_or_404(session, package_id)
    changes = body.model_dump(exclude_unset=True)
    nulls = [k for k, v in changes.items() if v is None and k in _NON_NULLABLE]
    if nulls:
        raise AppError(422, "validation_error", "Trường bắt buộc không được để trống", nulls)
    before = audit.snapshot(package, _TRACKED)
    for field, value in changes.items():
        setattr(package, field, value)
    package.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(package, _TRACKED))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="package",
            entity_id=package.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    await session.refresh(package)
    return package


@router.get("/{package_id}/overview", response_model=PackageOverview)
async def package_overview(
    package_id: uuid.UUID, _: Reader, session: SessionDep
) -> PackageOverview:
    package = await package_or_404(session, package_id)
    project = await get_single_project(session)
    contracts = [await contract_out(session, c) for c in await _contracts_of(session, package.id)]
    return PackageOverview(
        package=PackageOut.model_validate(package),
        project=await _project_out(session, project),
        contracts=contracts,
        needs_review=any(c.needs_review for c in contracts),
    )
