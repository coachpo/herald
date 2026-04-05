"""Pure-ASGI middleware for Herald FastAPI.

All middleware avoids ``BaseHTTPMiddleware`` because its ``call_next``
dispatches the downstream handler in a **separate task**.  asyncpg
connections are bound to the task that created them, so mixing tasks
causes ``RuntimeError: … Future … attached to a different loop``.

Using raw ASGI keeps everything in the same task.
"""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar
from typing import Any, MutableMapping

import structlog
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import get_settings

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class CorsMiddleware:
    """Custom CORS middleware matching Django implementation."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        origin = request.headers.get("origin")
        settings = get_settings()
        allowed = set(settings.cors_allowed_origins)

        if not (origin and origin in allowed):
            await self.app(scope, receive, send)
            return

        # Preflight
        if request.method == "OPTIONS" and request.headers.get(
            "access-control-request-method"
        ):
            response = Response(status_code=204)
            _set_cors_headers(response, request, origin)
            await response(scope, receive, send)
            return

        # Normal request – intercept response headers
        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("Access-Control-Allow-Origin", origin)
                headers.append(
                    "Access-Control-Allow-Methods",
                    "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                )
                requested = request.headers.get("access-control-request-headers")
                headers.append(
                    "Access-Control-Allow-Headers",
                    requested
                    or "Authorization, Content-Type, Accept, X-Herald-Ingest-Key",
                )
                headers.append("Access-Control-Max-Age", "600")
                # Vary
                existing_vary = headers.get("vary")
                if existing_vary:
                    if "Origin" not in {v.strip() for v in existing_vary.split(",")}:
                        headers.append("vary", "Origin")
                else:
                    headers.append("vary", "Origin")
            await send(message)

        await self.app(scope, receive, send_with_cors)


def _set_cors_headers(response: Response, request: Request, origin: str) -> None:
    response.headers["Access-Control-Allow-Origin"] = origin
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    )
    requested = request.headers.get("access-control-request-headers")
    if requested:
        response.headers["Access-Control-Allow-Headers"] = requested
    else:
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization, Content-Type, Accept, X-Herald-Ingest-Key"
        )
    response.headers["Access-Control-Max-Age"] = "600"
    response.headers["vary"] = "Origin"


# ---------------------------------------------------------------------------
# Request ID
# ---------------------------------------------------------------------------


class RequestIDMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx_var.set(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)

        async def send_with_rid(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-ID", rid)
            await send(message)

        try:
            await self.app(scope, receive, send_with_rid)
        finally:
            request_id_ctx_var.reset(token)
            structlog.contextvars.unbind_contextvars("request_id")


# ---------------------------------------------------------------------------
# Access Log
# ---------------------------------------------------------------------------


class AccessLogMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/health":
            await self.app(scope, receive, send)
            return

        logger = structlog.get_logger("access")
        start = time.monotonic()
        status_code: int | None = None

        async def send_with_log(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        await self.app(scope, receive, send_with_log)

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        logger.info(
            "request",
            method=scope.get("method", ""),
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )


# ---------------------------------------------------------------------------
# Starlette MutableHeaders helper
# ---------------------------------------------------------------------------


class MutableHeaders:
    """Thin wrapper to mutate ASGI ``http.response.start`` headers in-place."""

    def __init__(self, scope: MutableMapping[str, Any]) -> None:
        self._headers: list[tuple[bytes, bytes]] = list(scope.get("headers", []))
        scope["headers"] = self._headers

    def get(self, key: str) -> str | None:
        lower = key.lower().encode("latin-1")
        for k, v in self._headers:
            if k == lower:
                return v.decode("latin-1")
        return None

    def append(self, key: str, value: str) -> None:
        self._headers.append((key.lower().encode("latin-1"), value.encode("latin-1")))
