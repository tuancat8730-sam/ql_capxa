"""Login throttling and credential checks (SPEC 4.1)."""

from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, needs_rehash, verify_password
from app.models import User
from app.services import audit

MAX_FAILED_ATTEMPTS = 5
LOCK_DURATION = timedelta(minutes=15)

# Verified against when the email is unknown, so response time does not reveal which emails exist.
_DUMMY_HASH = hash_password("timing-equaliser")


def _invalid() -> AppError:
    return AppError(401, "invalid_credentials", "Email hoặc mật khẩu không đúng")


async def _fail(
    session: AsyncSession, user: User | None, email: str, request: Request, error: AppError
) -> AppError:
    audit.record(
        session,
        action="login",
        entity_type="user",
        entity_id=user.id if user else None,
        user_id=user.id if user else None,
        changes={"success": False, "email": email, "reason": error.code},
        request=request,
    )
    await session.commit()
    return error


async def authenticate(session: AsyncSession, email: str, password: str, request: Request) -> User:
    user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    now = datetime.now(UTC)

    if user is None or not user.is_active:
        verify_password(password, _DUMMY_HASH)
        raise await _fail(session, user, email, request, _invalid())

    if user.locked_until is not None:
        if user.locked_until > now:
            raise await _fail(
                session,
                user,
                email,
                request,
                AppError(
                    429,
                    "account_locked",
                    "Tài khoản tạm khóa 15 phút do nhập sai mật khẩu nhiều lần",
                ),
            )
        user.locked_until = None
        user.failed_attempts = 0

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + LOCK_DURATION
        raise await _fail(session, user, email, request, _invalid())

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    audit.record(
        session,
        action="login",
        entity_type="user",
        entity_id=user.id,
        user_id=user.id,
        changes={"success": True},
        request=request,
    )
    await session.commit()
    return user
