from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import SessionDep, require
from app.core.errors import AppError
from app.core.rbac import Level
from app.models import Organization, Package, Project, User
from app.schemas.project import ProjectOut, ProjectUpdate
from app.services import audit

router = APIRouter(prefix="/project", tags=["project"])

Reader = Annotated[User, Depends(require("project", Level.READ))]
Writer = Annotated[User, Depends(require("project", Level.WRITE))]

_TRACKED = (
    "name",
    "decision_maker",
    "total_investment",
    "funding_source",
    "start_year",
    "end_year",
    "location",
    "treasury_account",
    "description",
)


async def get_single_project(session: AsyncSession) -> Project:
    """One project in the MVP (SPEC section 5)."""
    project = (
        (
            await session.execute(
                select(Project).where(Project.deleted_at.is_(None)).order_by(Project.created_at)
            )
        )
        .scalars()
        .first()
    )
    if project is None:
        raise AppError(404, "not_found", "Chưa có dự án")
    return project


async def _project_out(session: AsyncSession, project: Project) -> ProjectOut:
    investor = (
        await session.get(Organization, project.investor_org_id)
        if project.investor_org_id
        else None
    )
    count = (
        await session.execute(
            select(func.count())
            .select_from(Package)
            .where(Package.project_id == project.id, Package.deleted_at.is_(None))
        )
    ).scalar_one()
    out = ProjectOut.model_validate(project)
    out.investor_name = investor.name if investor else None
    out.package_count = count
    return out


@router.get("", response_model=ProjectOut)
async def read_project(_: Reader, session: SessionDep) -> ProjectOut:
    return await _project_out(session, await get_single_project(session))


@router.patch("", response_model=ProjectOut)
async def update_project(
    body: ProjectUpdate, request: Request, user: Writer, session: SessionDep
) -> ProjectOut:
    project = await get_single_project(session)
    changes = body.model_dump(exclude_unset=True)
    if changes.get("name") is None and "name" in changes:
        raise AppError(422, "validation_error", "Tên dự án không được để trống")
    before = audit.snapshot(project, _TRACKED)
    for field, value in changes.items():
        setattr(project, field, value)
    project.updated_by = user.id
    delta = audit.diff(before, audit.snapshot(project, _TRACKED))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="project",
            entity_id=project.id,
            user_id=user.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    await session.refresh(project)
    return await _project_out(session, project)
