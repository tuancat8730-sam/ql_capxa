import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.deps import SessionDep, require_roles
from app.core.errors import AppError
from app.core.security import generate_temporary_password, hash_password
from app.models import User
from app.schemas.auth import UserOut
from app.schemas.common import Page, PaginationDep
from app.schemas.user import TempPasswordOut, UserCreate, UserUpdate, UserWithTempPassword
from app.services import audit

router = APIRouter(prefix="/users", tags=["users"])

AdminUser = Annotated[User, Depends(require_roles("admin"))]

_TRACKED = ("full_name", "phone", "role", "is_active")


def _snapshot(user: User) -> dict[str, object]:
    return {f: getattr(user, f) for f in _TRACKED}


async def _get_or_404(session: SessionDep, user_id: uuid.UUID) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "Không tìm thấy người dùng")
    return user


@router.get("", response_model=Page[UserOut])
async def list_users(
    _: AdminUser,
    session: SessionDep,
    pagination: PaginationDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    role: str | None = None,
    is_active: bool | None = None,
) -> Page[UserOut]:
    stmt = select(User)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if role:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await session.execute(
                stmt.order_by(User.created_at, User.email)
                .offset(pagination.offset)
                .limit(pagination.page_size)
            )
        )
        .scalars()
        .all()
    )
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in rows],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("", response_model=UserWithTempPassword, status_code=201)
async def create_user(
    body: UserCreate, request: Request, admin: AdminUser, session: SessionDep
) -> UserWithTempPassword:
    temp = generate_temporary_password()
    user = User(
        email=body.email,
        full_name=body.full_name,
        phone=body.phone,
        role=body.role,
        is_active=True,
        must_change_password=True,
        password_hash=hash_password(temp),
        created_by=admin.id,
        updated_by=admin.id,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppError(409, "conflict", "Email đã được sử dụng") from exc
    audit.record(
        session,
        action="create",
        entity_type="user",
        entity_id=user.id,
        user_id=admin.id,
        changes={"email": user.email, **_snapshot(user)},
        request=request,
    )
    await session.commit()
    await session.refresh(user)
    return UserWithTempPassword(
        **UserOut.model_validate(user).model_dump(), temporary_password=temp
    )


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: uuid.UUID, _: AdminUser, session: SessionDep) -> User:
    return await _get_or_404(session, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, request: Request, admin: AdminUser, session: SessionDep
) -> User:
    user = await _get_or_404(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        changes.get("is_active") is False or ("role" in changes and changes["role"] != user.role)
    ):
        raise AppError(400, "bad_request", "Không thể tự khóa hoặc đổi vai trò của chính mình")
    before = _snapshot(user)
    for field, value in changes.items():
        setattr(user, field, value)
    user.updated_by = admin.id
    if changes.get("is_active") is False:
        user.token_version += 1  # kick active sessions
    delta = audit.diff(before, _snapshot(user))
    if delta:
        audit.record(
            session,
            action="update",
            entity_type="user",
            entity_id=user.id,
            user_id=admin.id,
            changes=delta,
            request=request,
        )
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/{user_id}/reset-password", response_model=TempPasswordOut)
async def reset_password(
    user_id: uuid.UUID, request: Request, admin: AdminUser, session: SessionDep
) -> TempPasswordOut:
    user = await _get_or_404(session, user_id)
    temp = generate_temporary_password()
    user.password_hash = hash_password(temp)
    user.must_change_password = True
    user.token_version += 1
    user.failed_attempts = 0
    user.locked_until = None
    user.updated_by = admin.id
    audit.record(
        session,
        action="update",
        entity_type="user",
        entity_id=user.id,
        user_id=admin.id,
        changes={"credential": "reset"},
        request=request,
    )
    await session.commit()
    return TempPasswordOut(temporary_password=temp)
