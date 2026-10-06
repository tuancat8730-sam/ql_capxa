import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://qlda:qlda@localhost:5432/qlda_test"
)
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["COOKIE_SECURE"] = "false"  # test client talks plain http

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

import app.models  # noqa: E402, F401  (register tables)
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402
from app.models.user import ROLES  # noqa: E402

PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    yield


@pytest.fixture(autouse=True)
async def _clean_db() -> AsyncIterator[None]:
    from app.core import db

    yield
    async with db.get_sessionmaker()() as s:
        tables = ", ".join(t.name for t in reversed(Base.metadata.sorted_tables))
        await s.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        await s.commit()
    await db.get_engine().dispose()
    db._engine = None
    db._sessionmaker = None


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    from app.core import db

    async with db.get_sessionmaker()() as s:
        yield s


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def make_user(
    session: AsyncSession,
    role: str = "viewer",
    email: str | None = None,
    *,
    must_change_password: bool = False,
    is_active: bool = True,
) -> User:
    user = User(
        email=email or f"{role}@example.test",
        full_name=f"User {role}",
        role=role,
        is_active=is_active,
        password_hash=hash_password(PASSWORD),
        must_change_password=must_change_password,
    )
    session.add(user)
    await session.commit()
    return user


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def make_client_for():
    """Factory: returns an authenticated client for the given role."""

    async def _make(session: AsyncSession, role: str) -> httpx.AsyncClient:
        await make_user(session, role)
        transport = httpx.ASGITransport(app=create_app())
        c = httpx.AsyncClient(transport=transport, base_url="http://test")
        resp = await login(c, f"{role}@example.test")
        assert resp.status_code == 200, resp.text
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        return c

    return _make


ALL_ROLES = sorted(ROLES)
