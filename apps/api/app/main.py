from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.routers import (
    alerts,
    audit,
    auth,
    checklists,
    contracts,
    dashboard,
    documents,
    exports,
    finance,
    issues,
    meetings,
    packages,
    progress,
    project,
    risks,
    users,
)
from app.services.alert_jobs import WriteRefresh
from app.services.mailer import Mailer
from app.services.storage import Storage

# Writes under these prefixes cannot change an alert, so they never trigger an engine pass.
_NO_REFRESH_PREFIXES = ("/api/v1/auth", "/api/v1/alerts", "/api/v1/users", "/api/v1/audit")
_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def create_app(storage: Storage | None = None, mailer: Mailer | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="QLDA Cấp xã Lâm Đồng", version="0.1.0")
    app.state.storage = storage  # None -> S3Storage built lazily from settings
    app.state.mailer = mailer  # None -> built lazily from settings (smtp / ses / memory)
    app.state.write_refresh = WriteRefresh(lambda: app.state.mailer)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    if settings.alert_refresh_on_write:

        @app.middleware("http")
        async def refresh_alerts_after_write(request: Request, call_next):  # type: ignore[no-untyped-def]
            response = await call_next(request)
            path = request.url.path
            if (
                request.method in _WRITE_METHODS
                and response.status_code < 400
                and not path.startswith(_NO_REFRESH_PREFIXES)
            ):
                app.state.write_refresh.trigger()
            return response

    api = APIRouter(prefix="/api/v1")

    @api.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.get("/_echo", include_in_schema=False)
    async def echo(n: int) -> dict[str, int]:
        # Exercises request validation; removed once real routers exist.
        return {"n": n}

    api.include_router(auth.router)
    api.include_router(users.router)
    api.include_router(audit.router)
    api.include_router(project.router)
    api.include_router(packages.router)
    api.include_router(contracts.router)
    api.include_router(finance.router)
    api.include_router(documents.router)
    api.include_router(checklists.router)
    api.include_router(progress.router)
    api.include_router(exports.router)
    api.include_router(risks.router)
    api.include_router(issues.router)
    api.include_router(meetings.router)
    api.include_router(alerts.router)
    api.include_router(dashboard.router)
    app.include_router(api)
    return app


app = create_app()
