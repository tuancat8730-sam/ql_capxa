from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models import User
from app.seed.users import ensure_admin


async def test_creates_admin_who_can_use_the_temporary_password_at_once(
    session: AsyncSession,
) -> None:
    result = await ensure_admin(session, "Boss@Example.test", "Init1al-Passw0rd")
    assert result.created is True
    admin = (await session.execute(select(User))).scalar_one()
    assert admin.email == "boss@example.test"
    assert admin.role == "admin"
    assert admin.is_active and not admin.must_change_password
    assert verify_password("Init1al-Passw0rd", admin.password_hash)


async def test_generates_password_when_none_given(session: AsyncSession) -> None:
    result = await ensure_admin(session, "boss@example.test", None)
    assert result.password and len(result.password) >= 12
    admin = (await session.execute(select(User))).scalar_one()
    assert verify_password(result.password, admin.password_hash)


async def test_is_idempotent_and_never_overwrites_existing_password(session: AsyncSession) -> None:
    await ensure_admin(session, "boss@example.test", "Init1al-Passw0rd")
    again = await ensure_admin(session, "boss@example.test", "Different-Passw0rd")
    assert again.created is False and again.password is None
    admin = (await session.execute(select(User))).scalar_one()
    assert verify_password("Init1al-Passw0rd", admin.password_hash)
