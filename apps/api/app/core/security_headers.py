"""Security headers for every API response (SPEC 4.17: OWASP, CSP)."""

from collections.abc import Mapping

# The API only returns JSON, files and redirects, so nothing may load or embed anything.
_API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
# Swagger UI and ReDoc pull scripts and styles from a CDN.
_DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: "
    "https://fastapi.tiangolo.com; frame-ancestors 'none'"
)
_DOCS_PREFIXES = ("/docs", "/redoc")
_HSTS = "max-age=31536000; includeSubDomains"


def security_headers(path: str, *, secure: bool) -> Mapping[str, str]:
    """Headers to add for a request path; HSTS only when the deployment really is HTTPS."""
    headers = {
        "Content-Security-Policy": _DOCS_CSP if path.startswith(_DOCS_PREFIXES) else _API_CSP,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Resource-Policy": "same-site",
    }
    if secure:
        headers["Strict-Transport-Security"] = _HSTS
    return headers
