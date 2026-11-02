"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlmodel import Session

from financial_tracker_api.config import get_settings
from financial_tracker_api.db import engine, init_db
from financial_tracker_api.rate_limit import limiter
from financial_tracker_api.routers import auth, receipts, stats, stores
from financial_tracker_api.seed import seed_categories


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize database and seed data on startup."""
    get_settings().assert_secure()
    init_db()
    with Session(engine) as session:
        seed_categories(session)
    yield


def create_app() -> FastAPI:
    """Build the FastAPI app."""
    settings = get_settings()
    docs_url = "/docs" if settings.docs_enabled() else None
    redoc_url = "/redoc" if settings.docs_enabled() else None
    openapi_url = "/openapi.json" if settings.docs_enabled() else None
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(receipts.router)
    app.include_router(stats.router)
    app.include_router(stores.router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.environment}

    @app.exception_handler(ValueError)
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()


def main() -> None:
    """CLI entry used by the uv script."""
    import uvicorn

    uvicorn.run("financial_tracker_api.main:app", host="0.0.0.0", port=8000, reload=True)
