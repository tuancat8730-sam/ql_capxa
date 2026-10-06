from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.routers import (
    audit,
    auth,
    checklists,
    contracts,
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
from app.services.storage import Storage


def create_app(storage: Storage | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="QLDA Cấp xã Lâm Đồng", version="0.1.0")
    app.state.storage = storage  # None -> S3Storage built lazily from settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

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
    app.include_router(api)
    return app


app = create_app()
