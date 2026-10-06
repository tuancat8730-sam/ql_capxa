import httpx
import pytest

from app.main import create_app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health_ok(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_unknown_route_uses_error_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == "not_found"


async def test_validation_error_uses_error_envelope(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/v1/_echo", params={"n": "abc"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
