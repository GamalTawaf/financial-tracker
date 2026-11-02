"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
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

_SENSITIVE_FIELDS = frozenset(
    {"password", "refresh_token", "access_token", "token", "secret", "secret_key"}
)
_FIELD_LABELS = {
    "password": "Password",
    "email": "Email",
    "display_name": "Display name",
}


def _friendly_validation_detail(errors: list[Any]) -> str:
    """Build a safe, human-readable validation message (never echo secrets)."""
    parts: list[str] = []
    for err in errors:
        loc = [str(item) for item in err.get("loc", ()) if item not in ("body", "query", "path")]
        field = loc[-1] if loc else "field"
        label = _FIELD_LABELS.get(field, field.replace("_", " ").capitalize())
        msg = str(err.get("msg", "Invalid value"))
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        if field == "password" and "at least" in msg.lower():
            parts.append("Password must be at least 12 characters")
        elif field in _SENSITIVE_FIELDS:
            parts.append(msg if msg.lower().startswith("password") else f"{label}: {msg}")
        else:
            parts.append(f"{label}: {msg}")
    return "; ".join(parts) or "Invalid request"


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

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Strip raw ``input`` (can contain passwords) from the client response.
        return JSONResponse(
            status_code=422,
            content={"detail": _friendly_validation_detail(exc.errors())},
        )

    return app


app = create_app()


def main() -> None:
    """CLI entry used by the uv script."""
    import uvicorn

    uvicorn.run("financial_tracker_api.main:app", host="0.0.0.0", port=8000, reload=True)
