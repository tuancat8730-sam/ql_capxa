import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://qlda:qlda@localhost:5432/qlda_test"
)
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret"
os.environ["COOKIE_SECURE"] = "false"  # test client talks plain http
os.environ["MAIL_BACKEND"] = "memory"
os.environ["ALERT_REFRESH_ON_WRITE"] = "false"  # tests that want the hook turn it on explicitly

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402

import app.models  # noqa: E402, F401  (register tables)
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, Project, ProjectMember, User  # noqa: E402
from app.models.user import ROLES  # noqa: E402
from app.seed.project import PROJECT  # noqa: E402
from app.services.storage import MemoryStorage  # noqa: E402

PASSWORD = "Str0ng-Passw0rd!"


@pytest.fixture(scope="session", autouse=True)
async def _schema() -> AsyncIterator[None]:
    engine = create_async_engine(get_settings().database_url)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS unaccent"))
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
def storage() -> MemoryStorage:
    return MemoryStorage()


@pytest.fixture
async def client(storage: MemoryStorage) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app(storage=storage))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def seat_in_projects(session: AsyncSession, user: User) -> None:
    """Give the user a seat (their account role) in every project that already exists."""
    if user.role == "admin":
        return
    for (project_id,) in (await session.execute(select(Project.id))).all():
        exists = (
            await session.execute(
                select(ProjectMember.id).where(
                    ProjectMember.project_id == project_id, ProjectMember.user_id == user.id
                )
            )
        ).first()
        if not exists:
            session.add(ProjectMember(project_id=project_id, user_id=user.id, role=user.role))
    await session.commit()


async def ensure_default_project(session: AsyncSession) -> None:
    """Most tests just need *a* project to exist: the commune-level one, without its packages."""
    if (await session.execute(select(Project.id).limit(1))).first() is None:
        session.add(Project(**PROJECT))
        await session.commit()


async def make_user(
    session: AsyncSession,
    role: str = "viewer",
    email: str | None = None,
    *,
    must_change_password: bool = False,
    is_active: bool = True,
    seat: bool = True,
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
    if seat:
        await seat_in_projects(session, user)
    return user


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> httpx.Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.fixture
def make_client_for(storage: MemoryStorage):
    """Factory: returns an authenticated client for the given role."""

    async def _make(session: AsyncSession, role: str) -> httpx.AsyncClient:
        await ensure_default_project(session)
        existing = (
            await session.execute(select(User).where(User.email == f"{role}@example.test"))
        ).scalar_one_or_none()
        if existing is None:
            await make_user(session, role)
        else:  # a project created after the user still needs to seat them
            await seat_in_projects(session, existing)
        transport = httpx.ASGITransport(app=create_app(storage=storage))
        c = httpx.AsyncClient(transport=transport, base_url="http://test")
        resp = await login(c, f"{role}@example.test")
        assert resp.status_code == 200, resp.text
        c.headers["Authorization"] = f"Bearer {resp.json()['access_token']}"
        return c

    return _make


ALL_ROLES = sorted(ROLES)
