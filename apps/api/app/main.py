from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_error_handlers
from app.routers import audit, auth, users


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="QLDA Cấp xã Lâm Đồng", version="0.1.0")
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
    app.include_router(api)
    return app


app = create_app()
