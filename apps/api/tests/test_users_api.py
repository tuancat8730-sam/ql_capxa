import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog
from tests.conftest import ALL_ROLES, PASSWORD, login, make_user

NEW_USER = {"email": "new@example.test", "full_name": "Người Mới", "role": "technical"}


@pytest.mark.parametrize("role", [r for r in ALL_ROLES if r != "admin"])
async def test_non_admin_forbidden_on_user_endpoints(
    role: str, session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, role)
    assert (await c.get("/api/v1/users")).status_code == 403
    assert (await c.post("/api/v1/users", json=NEW_USER)).status_code == 403


async def test_admin_creates_lists_and_gets_user(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    created = await c.post("/api/v1/users", json=NEW_USER)
    assert created.status_code == 201
    body = created.json()
    assert body["must_change_password"] is True
    assert body["temporary_password"] and len(body["temporary_password"]) >= 12
    assert "password_hash" not in body

    listing = await c.get("/api/v1/users")
    assert listing.status_code == 200
    data = listing.json()
    assert set(data) == {"items", "total", "page", "page_size"}
    assert data["total"] == 2

    one = await c.get(f"/api/v1/users/{body['id']}")
    assert one.status_code == 200
    assert "temporary_password" not in one.json()


async def test_temporary_password_lets_new_user_login_and_forces_change(
    session: AsyncSession, make_client_for, client: httpx.AsyncClient
) -> None:
    c = await make_client_for(session, "admin")
    body = (await c.post("/api/v1/users", json=NEW_USER)).json()
    resp = await login(client, NEW_USER["email"], body["temporary_password"])
    assert resp.status_code == 200
    assert resp.json()["user"]["must_change_password"] is True


async def test_duplicate_email_conflict_case_insensitive(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    assert (await c.post("/api/v1/users", json=NEW_USER)).status_code == 201
    dup = await c.post("/api/v1/users", json={**NEW_USER, "email": "NEW@example.test"})
    assert dup.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {**NEW_USER, "role": "emperor"},
        {**NEW_USER, "email": "not-an-email"},
        {"email": "a@example.test"},
    ],
)
async def test_create_user_validation_422(
    payload: dict, session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    assert (await c.post("/api/v1/users", json=payload)).status_code == 422


async def test_patch_user_role_and_deactivate(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    uid = (await c.post("/api/v1/users", json=NEW_USER)).json()["id"]
    resp = await c.patch(f"/api/v1/users/{uid}", json={"role": "cost", "is_active": False})
    assert resp.status_code == 200
    assert resp.json()["role"] == "cost"
    assert resp.json()["is_active"] is False


async def test_admin_cannot_deactivate_or_demote_self(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    me = (await c.get("/api/v1/auth/me")).json()["id"]
    assert (await c.patch(f"/api/v1/users/{me}", json={"is_active": False})).status_code == 400
    assert (await c.patch(f"/api/v1/users/{me}", json={"role": "viewer"})).status_code == 400


async def test_users_cannot_be_deleted(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    uid = (await c.post("/api/v1/users", json=NEW_USER)).json()["id"]
    assert (await c.delete(f"/api/v1/users/{uid}")).status_code == 405


async def test_reset_password_returns_new_temp_password_and_revokes(
    session: AsyncSession, make_client_for, client: httpx.AsyncClient
) -> None:
    c = await make_client_for(session, "admin")
    await make_user(session, "viewer")
    uid = (await c.get("/api/v1/users", params={"q": "viewer"})).json()["items"][0]["id"]
    old = (await login(client, "viewer@example.test")).json()["access_token"]
    resp = await c.post(f"/api/v1/users/{uid}/reset-password")
    assert resp.status_code == 200
    temp = resp.json()["temporary_password"]
    assert (await login(client, "viewer@example.test", PASSWORD)).status_code == 401
    assert (
        await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old}"})
    ).status_code == 401
    again = await login(client, "viewer@example.test", temp)
    assert again.status_code == 200
    assert again.json()["user"]["must_change_password"] is True


async def test_reset_password_clears_lockout(
    session: AsyncSession, make_client_for, client: httpx.AsyncClient
) -> None:
    c = await make_client_for(session, "admin")
    user = await make_user(session, "viewer")
    for _ in range(5):
        await login(client, "viewer@example.test", "bad")
    assert (await login(client, "viewer@example.test")).status_code == 429
    temp = (await c.post(f"/api/v1/users/{user.id}/reset-password")).json()["temporary_password"]
    assert (await login(client, "viewer@example.test", temp)).status_code == 200


async def test_list_filters_and_pagination(session: AsyncSession, make_client_for) -> None:
    c = await make_client_for(session, "admin")
    for i in range(3):
        await c.post("/api/v1/users", json={**NEW_USER, "email": f"u{i}@example.test"})
    page = (await c.get("/api/v1/users", params={"page": 1, "page_size": 2})).json()
    assert len(page["items"]) == 2 and page["total"] == 4
    by_role = (await c.get("/api/v1/users", params={"role": "technical"})).json()
    assert by_role["total"] == 3
    assert (await c.get("/api/v1/users", params={"page_size": 101})).status_code == 422


async def test_user_changes_are_audited_without_secrets(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "admin")
    uid = (await c.post("/api/v1/users", json=NEW_USER)).json()["id"]
    await c.patch(f"/api/v1/users/{uid}", json={"role": "cost"})
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.entity_id == uid))).scalars().all()
    )
    assert {r.action for r in rows} == {"create", "update"}
    assert all(r.entity_type == "user" for r in rows)
    dumped = " ".join(str(r.changes) for r in rows)
    assert "password" not in dumped.lower() and "argon2" not in dumped
    upd = next(r for r in rows if r.action == "update")
    assert upd.changes["role"] == {"before": "technical", "after": "cost"}
