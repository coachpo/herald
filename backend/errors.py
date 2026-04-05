from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _build_error_body(
    *,
    status_code: int,
    detail: Any,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail}
    if errors is not None:
        body["errors"] = errors
    return body


def _coerce_http_detail(detail: Any) -> Any:
    if isinstance(detail, (str, dict, list)):
        return detail
    return str(detail)


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        return await unhandled_exception_handler(request, exc)
    return JSONResponse(
        status_code=exc.status_code,
        content=_build_error_body(
            status_code=exc.status_code,
            detail=_coerce_http_detail(exc.detail),
        ),
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        return await unhandled_exception_handler(request, exc)
    field_errors = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []))
        field_errors.append({"field": loc, "message": err.get("msg", "")})
    return JSONResponse(
        status_code=422,
        content=_build_error_body(
            status_code=422,
            detail="validation_error",
            errors=field_errors,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=_build_error_body(status_code=500, detail="internal_server_error"),
    )
