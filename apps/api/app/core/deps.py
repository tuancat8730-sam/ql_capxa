"""FastAPI dependencies: current user, role checks, RBAC enforcement."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import AppError
from app.core.rbac import Level, can
from app.core.scope import set_project_id
from app.core.security import decode_token
from app.models import Project, ProjectMember, User
from app.services.mailer import Mailer, build_mailer
from app.services.storage import Storage, build_storage

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_storage(request: Request) -> Storage:
    """App-wide object storage; tests inject `MemoryStorage` through `create_app(storage=...)`."""
    storage: Storage | None = request.app.state.storage
    if storage is None:
        storage = request.app.state.storage = build_storage(get_settings())
    return storage


StorageDep = Annotated[Storage, Depends(get_storage)]


async def get_mailer(request: Request) -> Mailer:
    """App-wide mailer; tests inject `MemoryMailer` through `create_app(mailer=...)`."""
    mailer: Mailer | None = request.app.state.mailer
    if mailer is None:
        mailer = request.app.state.mailer = build_mailer()
    return mailer


MailerDep = Annotated[Mailer, Depends(get_mailer)]


async def _authenticate(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> User:
    if creds is None:
        raise AppError(401, "unauthorized", "Chưa đăng nhập")
    claims = decode_token(creds.credentials, "access")
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active or claims.get("tv") != user.token_version:
        raise AppError(401, "unauthorized", "Phiên đăng nhập không hợp lệ hoặc đã hết hạn")
    return user


async def current_user_allow_pw_change(user: Annotated[User, Depends(_authenticate)]) -> User:
    """For the few endpoints a user with a temporary password may call (me, change-password)."""
    return user


async def current_user(user: Annotated[User, Depends(_authenticate)]) -> User:
    return user


CurrentUser = Annotated[User, Depends(current_user)]
CurrentUserAllowPwChange = Annotated[User, Depends(current_user_allow_pw_change)]


@dataclass(frozen=True)
class ProjectContext:
    """The project a request works on and the role the caller has in it."""

    project: Project
    role: str

    def can(self, resource: str, needed: Level) -> bool:
        return can(self.role, resource, needed)


def _parse_project_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise AppError(400, "bad_request", "X-Project-Id không hợp lệ") from exc


async def _live_project(session: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise AppError(404, "not_found", "Không tìm thấy dự án")
    return project


async def resolve_project(
    session: AsyncSession, user: User, project_id: uuid.UUID | None
) -> ProjectContext:
    """Pick the project of a request and the caller's role in it.

    An explicit id needs a membership (system admins need none). Without an id the caller's only
    project is used; a system admin with no membership falls back to the oldest project.
    """
    is_admin = user.role == "admin"
    if project_id is not None:
        project = await _live_project(session, project_id)
        if is_admin:
            return ProjectContext(project, "admin")
        role = (
            await session.execute(
                select(ProjectMember.role).where(
                    ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
                )
            )
        ).scalar_one_or_none()
        if role is None:
            raise AppError(403, "forbidden", "Bạn không thuộc dự án này")
        return ProjectContext(project, role)

    rows = (
        await session.execute(
            select(Project, ProjectMember.role)
            .join(ProjectMember, ProjectMember.project_id == Project.id)
            .where(
                ProjectMember.user_id == user.id,
                Project.deleted_at.is_(None),
                Project.is_archived.is_(False),
            )
            .order_by(Project.created_at)
        )
    ).all()
    if len(rows) > 1:
        raise AppError(400, "bad_request", "Chưa chọn dự án (thiếu X-Project-Id)")
    if rows:
        project, role = rows[0]
        return ProjectContext(project, "admin" if is_admin else role)
    if is_admin:
        first = (
            (
                await session.execute(
                    select(Project)
                    .where(Project.deleted_at.is_(None), Project.is_archived.is_(False))
                    .order_by(Project.created_at)
                )
            )
            .scalars()
            .first()
        )
        if first is not None:
            return ProjectContext(first, "admin")
        raise AppError(404, "not_found", "Chưa có dự án")
    raise AppError(403, "forbidden", "Bạn chưa được thêm vào dự án nào")


async def project_context(
    user: CurrentUser,
    session: SessionDep,
    x_project_id: Annotated[str | None, Header()] = None,
) -> ProjectContext:
    ctx = await resolve_project(
        session, user, _parse_project_id(x_project_id) if x_project_id else None
    )
    user.set_project_role(ctx.role)
    set_project_id(ctx.project.id)
    return ctx


ProjectCtx = Annotated[ProjectContext, Depends(project_context)]


async def _current_project(ctx: ProjectCtx) -> Project:
    return ctx.project


ProjectDep = Annotated[Project, Depends(_current_project)]


def require(resource: str, level: Level) -> Callable[..., Awaitable[User]]:
    """Dependency factory enforcing the SPEC section 8 matrix for `resource` at `level`.

    The role checked is the caller's role in the request's project.
    """

    async def _dep(user: CurrentUser, ctx: ProjectCtx) -> User:
        if not ctx.can(resource, level):
            raise AppError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
        return user

    return _dep


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    """The caller's role in the request's project must be one of `roles`."""

    async def _dep(user: CurrentUser, ctx: ProjectCtx) -> User:
        if ctx.role not in roles:
            raise AppError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
        return user

    return _dep


async def _system_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
    return user


# System-wide administration (accounts, new projects): not tied to any one project.
SystemAdmin = Annotated[User, Depends(_system_admin)]
