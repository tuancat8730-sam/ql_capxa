import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, ProjectDep, SessionDep, SystemAdmin, require
from app.core.errors import AppError
from app.core.project_types import modules_for
from app.core.rbac import Level
from app.models import Organization, Package, Project, ProjectMember, User
from app.schemas.project import (
    MemberIn,
    MemberOut,
    ProjectCreate,
    ProjectOut,
    ProjectSummary,
    ProjectUpdate,
)
from app.services import audit

router = APIRouter(prefix="/project", tags=["project"])
projects_router = APIRouter(prefix="/projects", tags=["projects"])

Reader = Annotated[User, Depends(require("project", Level.READ))]
Writer = Annotated[User, Depends(require("project", Level.WRITE))]

_TRACKED = (
    "name",
    "short_name",
    "decision_maker",
    "total_investment",
    "funding_source",
    "start_year",
    "end_year",
    "location",
    "treasury_account",
    "description",
)


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
async def read_project(_: Reader, session: SessionDep, project: ProjectDep) -> ProjectOut:
    return await _project_out(session, project)


@router.patch("", response_model=ProjectOut)
async def update_project(
    body: ProjectUpdate, request: Request, user: Writer, session: SessionDep, project: ProjectDep
) -> ProjectOut:
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


# --- the projects a user can switch between --------------------------------------------------


def _summary(project: Project, role: str) -> ProjectSummary:
    return ProjectSummary(
        id=project.id,
        code=project.code,
        name=project.name,
        short_name=project.short_name,
        project_type=project.project_type,
        role=role,
        modules=modules_for(project.project_type),
        is_archived=project.is_archived,
    )


@projects_router.get("", response_model=list[ProjectSummary])
async def my_projects(user: CurrentUser, session: SessionDep) -> list[ProjectSummary]:
    """Projects the caller works on; a system admin sees every project."""
    live = Project.deleted_at.is_(None)
    if user.role == "admin":
        rows = await session.execute(select(Project).where(live).order_by(Project.created_at))
        return [_summary(p, "admin") for p in rows.scalars()]
    pairs = await session.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(live, ProjectMember.user_id == user.id, Project.is_archived.is_(False))
        .order_by(Project.created_at)
    )
    return [_summary(p, role) for p, role in pairs.all()]


@projects_router.post("", response_model=ProjectSummary, status_code=201)
async def create_project(
    body: ProjectCreate, request: Request, admin: SystemAdmin, session: SessionDep
) -> ProjectSummary:
    project = Project(created_by=admin.id, updated_by=admin.id, **body.model_dump())
    session.add(project)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "conflict", "Mã dự án đã tồn tại") from exc
    audit.record(
        session,
        action="create",
        entity_type="project",
        entity_id=project.id,
        user_id=admin.id,
        changes={"code": project.code, "project_type": project.project_type},
        request=request,
    )
    await session.commit()
    await session.refresh(project)
    return _summary(project, "admin")


async def _project_or_404(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise AppError(404, "not_found", "Không tìm thấy dự án")
    return project


@projects_router.get("/{project_id}/members", response_model=list[MemberOut])
async def list_members(
    project_id: uuid.UUID, _: SystemAdmin, session: SessionDep
) -> list[MemberOut]:
    await _project_or_404(session, project_id)
    rows = await session.execute(
        select(User, ProjectMember.role)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id)
        .order_by(User.full_name)
    )
    return [
        MemberOut(
            user_id=u.id,
            email=u.email,
            full_name=u.full_name,
            role=role,
            is_active=u.is_active,
        )
        for u, role in rows.all()
    ]


@projects_router.put("/{project_id}/members/{user_id}", response_model=MemberOut)
async def set_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberIn,
    request: Request,
    admin: SystemAdmin,
    session: SessionDep,
) -> MemberOut:
    """Seat a user in the project or change their role there."""
    await _project_or_404(session, project_id)
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "Không tìm thấy người dùng")
    member = (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    before = member.role if member else None
    if member is None:
        member = ProjectMember(
            project_id=project_id,
            user_id=user_id,
            role=body.role,
            created_by=admin.id,
            updated_by=admin.id,
        )
        session.add(member)
    else:
        member.role = body.role
        member.updated_by = admin.id
    if before != body.role:
        audit.record(
            session,
            action="update",
            entity_type="project_member",
            entity_id=user_id,
            user_id=admin.id,
            changes={"role": {"before": before, "after": body.role}, "project_id": project_id},
            request=request,
        )
    await session.commit()
    return MemberOut(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=body.role,
        is_active=user.is_active,
    )


@projects_router.delete("/{project_id}/members/{user_id}", status_code=204)
async def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    request: Request,
    admin: SystemAdmin,
    session: SessionDep,
) -> Response:
    await _project_or_404(session, project_id)
    member = (
        await session.execute(
            select(ProjectMember).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise AppError(404, "not_found", "Người dùng không thuộc dự án")
    audit.record(
        session,
        action="delete",
        entity_type="project_member",
        entity_id=user_id,
        user_id=admin.id,
        changes={"role": member.role, "project_id": project_id},
        request=request,
    )
    await session.delete(member)
    await session.commit()
    return Response(status_code=204)
