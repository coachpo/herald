from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version as package_version
from pathlib import Path

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .database import dispose_database_state, get_sessionmaker
from .errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from .logging_config import setup_logging
from .middleware import AccessLogMiddleware, RateLimitMiddleware, RequestIDMiddleware
from .schemas import HealthResponse
from .routes import router, auth_router, ingest_router


ROOT_VERSION_PATH = Path(__file__).resolve().parent.parent / "VERSION"


def _get_repo_version() -> str:
    try:
        version = ROOT_VERSION_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"
    return version or "unknown"


def _get_app_version() -> str:
    env_version = os.environ.get("APP_VERSION")
    if env_version:
        return env_version
    try:
        return package_version("herald-backend")
    except PackageNotFoundError:
        return _get_repo_version()


_APP_VERSION = _get_app_version()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("app_startup", version=_APP_VERSION)
    yield
    logger.info("app_shutdown")
    await dispose_database_state()


def create_app() -> FastAPI:
    setup_logging()

    settings = get_settings()
    try:
        from .observability import init_sentry
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        init_sentry(extra_integrations=(StarletteIntegration(), FastApiIntegration()))
    except ImportError:
        pass

    app = FastAPI(title="Herald FastAPI", lifespan=lifespan)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    from starlette.middleware.cors import CORSMiddleware

    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Herald-Ingest-Key"],
        max_age=600,
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse | JSONResponse:
        db_status = "unavailable"
        try:
            async with get_sessionmaker()() as session:
                await session.execute(text("SELECT 1"))
                db_status = "connected"
        except Exception:
            pass

        status = "ok" if db_status == "connected" else "degraded"
        resp = HealthResponse(status=status, database=db_status, version=_APP_VERSION)
        if db_status != "connected":
            return JSONResponse(status_code=503, content=resp.model_dump())
        return resp

    app.include_router(auth_router)
    app.include_router(router)
    app.include_router(ingest_router)

    return app
