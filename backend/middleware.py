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

import structlog
from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .config import get_settings

request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


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
# Rate limit
# ---------------------------------------------------------------------------


class RateLimitMiddleware:
    """In-process token buckets. Single-instance deployment only.

    ponytail: per-process buckets; move to a shared store if this ever runs >1 replica.
    """

    _AUTH_PATHS = {"/api/auth/login", "/api/auth/signup", "/api/auth/refresh"}

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._buckets: dict[str, tuple[float, float]] = {}

    def _match(self, scope: Scope) -> tuple[str, int] | None:
        if scope.get("method") != "POST":
            return None
        path = scope.get("path", "")
        settings = get_settings()
        client = scope.get("client") or ("", 0)
        if path.startswith("/api/ingest/"):
            segment = path.rsplit("/", 1)[-1]
            try:
                canonical = uuid.UUID(segment).hex
            except ValueError:
                canonical = segment[:64]
            return (
                f"ingest:{client[0]}:{canonical}",
                settings.rate_limit_ingest_per_minute,
            )
        if path in self._AUTH_PATHS:
            return (f"auth:{client[0]}", settings.rate_limit_auth_per_minute)
        return None

    def _allow(self, key: str, per_minute: int) -> bool:
        now = time.monotonic()
        tokens, last = self._buckets.get(key, (float(per_minute), now))
        tokens = min(float(per_minute), tokens + (now - last) * per_minute / 60.0)
        if tokens < 1.0:
            self._buckets[key] = (tokens, now)
            return False
        if len(self._buckets) > 10_000:
            cutoff = now - 120.0
            stale = [k for k, (_, ts) in self._buckets.items() if ts < cutoff]
            for stale_key in stale:
                del self._buckets[stale_key]
            if len(self._buckets) > 10_000:
                self._buckets.clear()
        self._buckets[key] = (tokens - 1.0, now)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        matched = self._match(scope)
        if matched and not self._allow(*matched):
            response = Response(
                content=b'{"detail":"rate_limited"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
