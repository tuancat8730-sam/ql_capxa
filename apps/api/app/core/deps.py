"""FastAPI dependencies: current user, role checks, RBAC enforcement."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError
from app.core.rbac import Level, can
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


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
    if user.must_change_password:
        raise AppError(403, "password_change_required", "Bạn cần đổi mật khẩu trước khi tiếp tục")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
CurrentUserAllowPwChange = Annotated[User, Depends(current_user_allow_pw_change)]


def require(resource: str, level: Level) -> Callable[[User], Awaitable[User]]:
    """Dependency factory enforcing the SPEC section 8 matrix for `resource` at `level`."""

    async def _dep(user: CurrentUser) -> User:
        if not can(user.role, resource, level):
            raise AppError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
        return user

    return _dep


def require_roles(*roles: str) -> Callable[[User], Awaitable[User]]:
    async def _dep(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AppError(403, "forbidden", "Bạn không có quyền thực hiện thao tác này")
        return user

    return _dep
