"""M8: every response carries the security headers (SPEC 4.17)."""

import pytest

from app.core.security_headers import security_headers


def test_api_paths_get_a_locked_down_csp() -> None:
    h = security_headers("/api/v1/health", secure=False)
    assert h["Content-Security-Policy"].startswith("default-src 'none'")
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert h["Referrer-Policy"] == "no-referrer"
    assert "camera=()" in h["Permissions-Policy"]


@pytest.mark.parametrize("path", ["/docs", "/docs/oauth2-redirect", "/redoc"])
def test_docs_pages_may_load_their_scripts(path: str) -> None:
    csp = security_headers(path, secure=False)["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in csp and "frame-ancestors 'none'" in csp


def test_hsts_only_on_https_deployments() -> None:
    assert "Strict-Transport-Security" not in security_headers("/", secure=False)
    assert "max-age=31536000" in security_headers("/", secure=True)["Strict-Transport-Security"]


async def test_headers_are_on_success_error_and_unauthorised_responses(client) -> None:
    for url, status in (("/api/v1/health", 200), ("/api/v1/nope", 404), ("/api/v1/alerts", 401)):
        r = await client.get(url)
        assert r.status_code == status
        assert r.headers["x-content-type-options"] == "nosniff", url
        assert r.headers["content-security-policy"].startswith("default-src 'none'"), url
        assert r.headers["x-frame-options"] == "DENY", url


async def test_hsts_follows_the_cookie_secure_setting(client, monkeypatch) -> None:
    import httpx

    from app.core.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    try:
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/health")
        assert "max-age=31536000" in r.headers["strict-transport-security"]
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
    plain = await client.get("/api/v1/health")
    assert "strict-transport-security" not in plain.headers
