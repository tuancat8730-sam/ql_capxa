from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, User
from tests.conftest import PASSWORD, login, make_user


async def test_login_success_returns_token_and_cookie(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "director")
    resp = await login(client, "director@example.test")
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "director"
    assert "password_hash" not in body["user"]
    cookie = resp.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


async def test_login_wrong_password_and_unknown_email_same_error(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "director")
    bad_pw = await login(client, "director@example.test", "nope")
    unknown = await login(client, "ghost@example.test", "nope")
    assert bad_pw.status_code == unknown.status_code == 401
    assert (
        bad_pw.json()["error"]["code"] == unknown.json()["error"]["code"] == "invalid_credentials"
    )


async def test_inactive_user_cannot_login(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await make_user(session, "viewer", is_active=False)
    resp = await login(client, "viewer@example.test")
    assert resp.status_code == 401


async def test_lockout_after_five_failures(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "viewer")
    for _ in range(5):
        r = await login(client, "viewer@example.test", "bad")
        assert r.status_code == 401
    locked = await login(client, "viewer@example.test", PASSWORD)  # correct pw still refused
    assert locked.status_code == 429
    assert locked.json()["error"]["code"] == "account_locked"


async def test_four_failures_do_not_lock_and_success_resets_counter(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "viewer")
    for _ in range(4):
        await login(client, "viewer@example.test", "bad")
    assert (await login(client, "viewer@example.test")).status_code == 200
    for _ in range(4):
        await login(client, "viewer@example.test", "bad")
    assert (await login(client, "viewer@example.test")).status_code == 200


async def test_lock_expires_after_15_minutes(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, "viewer")
    for _ in range(5):
        await login(client, "viewer@example.test", "bad")
    await session.refresh(user)
    assert user.locked_until is not None
    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)
    await session.commit()
    assert (await login(client, "viewer@example.test")).status_code == 200


async def test_lock_duration_is_15_minutes(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, "viewer")
    for _ in range(5):
        await login(client, "viewer@example.test", "bad")
    await session.refresh(user)
    assert user.locked_until is not None
    delta = user.locked_until - datetime.now(UTC)
    assert timedelta(minutes=14) < delta <= timedelta(minutes=15)


async def test_me_requires_token(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_me_returns_current_user(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await make_user(session, "cost")
    tok = (await login(client, "cost@example.test")).json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "cost@example.test"


async def test_refresh_issues_new_access_token(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "cost")
    await login(client, "cost@example.test")  # cookie jar keeps refresh_token
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_refresh_without_cookie_401(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_access_token_cannot_be_used_as_refresh(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "cost")
    tok = (await login(client, "cost@example.test")).json()["access_token"]
    client.cookies.set("refresh_token", tok)
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_logout_clears_refresh_cookie(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "cost")
    await login(client, "cost@example.test")
    assert (await client.post("/api/v1/auth/logout")).status_code == 204
    assert (await client.post("/api/v1/auth/refresh")).status_code == 401


async def test_change_password_flow_and_revokes_old_tokens(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "cost", must_change_password=True)
    resp = await login(client, "cost@example.test")
    assert resp.json()["user"]["must_change_password"] is True
    h = {"Authorization": f"Bearer {resp.json()['access_token']}"}
    bad = await client.post(
        "/api/v1/auth/change-password",
        headers=h,
        json={"current_password": "wrong", "new_password": "An0ther-Str0ng!"},
    )
    assert bad.status_code == 400
    ok = await client.post(
        "/api/v1/auth/change-password",
        headers=h,
        json={"current_password": PASSWORD, "new_password": "An0ther-Str0ng!"},
    )
    assert ok.status_code == 204
    # old access token revoked via token_version
    assert (await client.get("/api/v1/auth/me", headers=h)).status_code == 401
    # new password works, flag cleared
    again = await login(client, "cost@example.test", "An0ther-Str0ng!")
    assert again.status_code == 200
    assert again.json()["user"]["must_change_password"] is False


async def test_weak_new_password_rejected(client: httpx.AsyncClient, session: AsyncSession) -> None:
    await make_user(session, "cost")
    tok = (await login(client, "cost@example.test")).json()["access_token"]
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert resp.status_code == 422


async def test_must_change_password_blocks_other_endpoints(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await make_user(session, "admin", must_change_password=True)
    tok = (await login(client, "admin@example.test")).json()["access_token"]
    resp = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "password_change_required"


async def test_deactivated_user_token_rejected(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    user = await make_user(session, "cost")
    tok = (await login(client, "cost@example.test")).json()["access_token"]
    user.is_active = False
    await session.commit()
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert resp.status_code == 401


async def test_login_is_audited(client: httpx.AsyncClient, session: AsyncSession) -> None:
    user = await make_user(session, "cost")
    await login(client, "cost@example.test")
    await login(client, "cost@example.test", "bad")
    rows = (
        (await session.execute(select(AuditLog).where(AuditLog.action == "login"))).scalars().all()
    )
    assert len(rows) == 2
    ok = [r for r in rows if r.user_id == user.id]
    assert ok, "successful login must record the user id"
    assert any(r.changes and r.changes.get("success") is False for r in rows)
    assert all(
        "password" not in str(r.changes).lower() or "success" in str(r.changes) for r in rows
    )
    refreshed = (await session.execute(select(User).where(User.id == user.id))).scalar_one()
    assert refreshed.last_login_at is not None
