import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..database import get_session
from ..models import IngestMessageResponse
from ..services.ingest import (
    authenticate_ingest_request,
    create_ingest_message,
    validate_ingest_payload,
)
from ..services.exceptions import IngestError

router = APIRouter()

_MAX_INGEST_BYTES = 1048576


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
)
@router.post("/ingest/{endpoint_id}", include_in_schema=False)
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
            message_id = await create_ingest_message(
                session,
                endpoint_id=authenticated.endpoint_id,
                user_id=authenticated.user_id,
                payload=payload,
                headers=headers,
                query_params=query_params,
                remote_ip=remote_ip,
                user_agent=user_agent,
                content_type=ct_base or None,
            )
        except IngestError as exc:
            return _json_error(code=exc.code, message=exc.message, status=exc.status)

        return JSONResponse(
            IngestMessageResponse(message_id=message_id).model_dump(mode="json"),
            status_code=201,
        )

    return _json_error(code="internal_error", message="internal error", status=500)
