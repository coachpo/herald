import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import get_session
from ..schemas import IngestMessageResponse
from ..services.ingest import (
    authenticate_ingest_request,
    create_ingest_message,
    validate_ingest_payload,
)
from ..services.exceptions import IngestError

router = APIRouter()

_MAX_INGEST_BYTES = 1048576
_RELAY_VIA_RE = re.compile("[^a-z,]")


def _json_error(
    *, code: str, message: str, status: int, details: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse(body, status_code=status)


@router.post(
    "/api/ingest/{endpoint_id}",
    response_model=IngestMessageResponse,
    status_code=201,
    responses={
        200: {
            "description": "Duplicate relay message",
            "model": IngestMessageResponse,
        },
    },
    openapi_extra={
        "parameters": [
            {
                "name": "X-Herald-Ingest-Key",
                "in": "header",
                "required": True,
                "schema": {"type": "string"},
                "description": "Raw ingest endpoint key",
            },
            {
                "name": "X-Herald-Message-Id",
                "in": "header",
                "required": False,
                "schema": {"type": "string", "format": "uuid"},
                "description": "Relay-provided idempotency id",
            },
            {
                "name": "X-Herald-Received-At",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Relay-provided receive timestamp",
            },
            {
                "name": "X-Herald-Relay-Via",
                "in": "header",
                "required": False,
                "schema": {"type": "string"},
                "description": "Comma-separated relay path",
            },
        ],
    },
)
async def ingest_message(endpoint_id: str, request: Request) -> JSONResponse:
    content_type = request.headers.get("content-type", "")
    ingest_key = request.headers.get("x-herald-ingest-key") or ""
    headers = dict(request.headers)
    query_params = dict(request.query_params)
    remote_ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent")

    async for session in get_session():
        try:
            authenticated = await authenticate_ingest_request(
                session,
                endpoint_id_raw=endpoint_id,
                ingest_key=ingest_key,
            )
            relay_message_id, relay_received_at, relay_via = _parse_relay_headers(request)
            ct_base = content_type.split(";", 1)[0].strip().lower()
            if ct_base != "application/json":
                return _json_error(
                    code="unsupported_media_type",
                    message="Content-Type must be application/json",
                    status=415,
                )

            body_bytes = await request.body()
            if len(body_bytes) > _MAX_INGEST_BYTES:
                return _json_error(
                    code="payload_too_large",
                    message="payload too large",
                    status=413,
                )

            try:
                raw_text = body_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return _json_error(
                    code="invalid_utf8",
                    message="invalid utf-8",
                    status=400,
                )

            try:
                data = json.loads(raw_text)
            except (json.JSONDecodeError, ValueError):
                return _json_error(
                    code="invalid_json",
                    message="invalid JSON",
                    status=400,
                )

            payload = validate_ingest_payload(data)
            message_id, duplicate = await create_ingest_message(
                session,
                endpoint_id=authenticated.endpoint_id,
                user_id=authenticated.user_id,
                payload=payload,
                headers=headers,
                query_params=query_params,
                remote_ip=remote_ip,
                user_agent=user_agent,
                content_type=ct_base or None,
                message_id=relay_message_id,
                received_at=relay_received_at,
                relay_via=relay_via,
            )
        except IngestError as exc:
            return _json_error(code=exc.code, message=exc.message, status=exc.status)

        body = {"message_id": message_id}
        if duplicate:
            body["duplicate"] = True
        return JSONResponse(
            IngestMessageResponse(**body).model_dump(mode="json", exclude_defaults=True),
            status_code=200 if duplicate else 201,
        )

    return _json_error(code="internal_error", message="internal error", status=500)


def _parse_relay_headers(request: Request) -> tuple[UUID | None, datetime | None, str | None]:
    raw_id = (request.headers.get("x-herald-message-id") or "").strip()
    message_id = None
    if raw_id:
        try:
            message_id = UUID(raw_id)
        except ValueError as exc:
            raise IngestError(
                code="invalid_relay_message_id",
                message="invalid relay message id",
                status=422,
            ) from exc

    received_at = None
    raw_received = (request.headers.get("x-herald-received-at") or "").strip()
    if raw_received:
        try:
            parsed = datetime.fromisoformat(raw_received.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            if abs(now - parsed.astimezone(timezone.utc)) <= timedelta(hours=48):
                received_at = parsed.astimezone(timezone.utc)
        except ValueError:
            received_at = None

    raw_via = (request.headers.get("x-herald-relay-via") or "").lower()
    relay_via = _RELAY_VIA_RE.sub("", raw_via)[:64] or None
    return message_id, received_at, relay_via
