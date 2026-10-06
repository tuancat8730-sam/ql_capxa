import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import ALL_ROLES


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_audit_log_access_matches_matrix(
    role: str, session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, role)
    resp = await c.get("/api/v1/audit-log")
    assert resp.status_code == (200 if role in {"admin", "director"} else 403)


async def test_audit_log_lists_login_newest_first_with_filters(
    session: AsyncSession, make_client_for
) -> None:
    c = await make_client_for(session, "admin")  # logging in wrote one 'login' row
    await c.post(
        "/api/v1/users",
        json={"email": "x@example.test", "full_name": "X", "role": "viewer"},
    )
    data = (await c.get("/api/v1/audit-log")).json()
    assert set(data) == {"items", "total", "page", "page_size"}
    assert data["total"] >= 2
    stamps = [i["ts"] for i in data["items"]]
    assert stamps == sorted(stamps, reverse=True)
    only_login = (await c.get("/api/v1/audit-log", params={"action": "login"})).json()
    assert only_login["total"] == 1
    only_user = (await c.get("/api/v1/audit-log", params={"entity_type": "user"})).json()
    assert {i["entity_type"] for i in only_user["items"]} == {"user"}
