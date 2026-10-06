"""Bootstrap the first administrator (SPEC 4.1: first login forces a password change)."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import generate_temporary_password, hash_password
from app.models import User


@dataclass(frozen=True)
class AdminResult:
    created: bool
    email: str
    password: str | None  # only set when the account was created in this call


async def ensure_admin(session: AsyncSession, email: str, password: str | None) -> AdminResult:
    email = email.strip().lower()
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing is not None:
        return AdminResult(created=False, email=email, password=None)
    password = password or generate_temporary_password()
    session.add(
        User(
            email=email,
            full_name="Quản trị hệ thống",
            role="admin",
            is_active=True,
            must_change_password=True,
            password_hash=hash_password(password),
        )
    )
    await session.commit()
    return AdminResult(created=True, email=email, password=password)
