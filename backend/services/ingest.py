from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone as tz
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.tokens import hash_token
from ..core.redaction import redact_headers
from ..core.rules import rule_matches_message
from ..database import get_tables, serialize_uuid
from .exceptions import IngestError

_ALLOWED_TOP_LEVEL_KEYS = {
    "title",
    "body",
    "group",
    "priority",
    "tags",
    "url",
    "extras",
}


@dataclass(frozen=True)
class IngestPayload:
    title: str | None
    body: str
    group: str | None
    priority: int
    tags: list[str]
    url: str | None
    extras: dict[str, str]


@dataclass(frozen=True)
class AuthenticatedEndpoint:
    endpoint_id: UUID
    user_id: UUID


def _auth_error() -> IngestError:
    return IngestError(
        code="not_authenticated",
        message="unauthorized",
        status=401,
    )


def _validation_error(message: str) -> IngestError:
    return IngestError(code="validation_error", message=message, status=422)


def _validate_url(value: str) -> bool:
    try:
        result = urlparse(value)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _normalized_url(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _parse_endpoint_id(endpoint_id_raw: str) -> UUID:
    try:
        return UUID(endpoint_id_raw)
    except ValueError:
        try:
            return UUID(hex=endpoint_id_raw)
        except ValueError as exc:
            raise _auth_error() from exc


def _rule_filter_dict(filter_json: Any) -> dict[str, Any]:
    if isinstance(filter_json, str):
        try:
            filter_json = json.loads(filter_json)
        except (json.JSONDecodeError, ValueError):
            return {}
    if isinstance(filter_json, dict):
        return filter_json
    return {}


def validate_ingest_payload(data: dict[str, Any]) -> IngestPayload:
    if not isinstance(data, dict):
        raise _validation_error("request body must be a JSON object")

    unknown_keys = set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
    if unknown_keys:
        raise _validation_error(f"unknown keys: {', '.join(sorted(unknown_keys))}")

    body_val = data.get("body")
    if body_val is None or not isinstance(body_val, str) or not body_val.strip():
        raise _validation_error("'body' is required and must be a non-empty string")

    title_val = data.get("title")
    if title_val is not None and not isinstance(title_val, str):
        raise _validation_error("'title' must be a string")

    group_val = data.get("group")
    if group_val is not None and not isinstance(group_val, str):
        raise _validation_error("'group' must be a string")

    priority_val = data.get("priority", 3)
    if not isinstance(priority_val, int) or isinstance(priority_val, bool):
        raise _validation_error("'priority' must be an integer")
    if priority_val < 1 or priority_val > 5:
        raise _validation_error("'priority' must be between 1 and 5")

    tags_val = data.get("tags", [])
    if not isinstance(tags_val, list):
        raise _validation_error("'tags' must be an array of strings")
    for index, tag in enumerate(tags_val):
        if not isinstance(tag, str):
            raise _validation_error(f"'tags[{index}]' must be a string")

    url_val = data.get("url")
    if url_val is not None:
        if not isinstance(url_val, str):
            raise _validation_error("'url' must be a string")
        if url_val.strip() and not _validate_url(url_val.strip()):
            raise _validation_error("'url' must be a valid URL")

    extras_val = data.get("extras", {})
    if not isinstance(extras_val, dict):
        raise _validation_error("'extras' must be an object")
    for key, value in extras_val.items():
        if not isinstance(value, str):
            raise _validation_error(f"'extras.{key}' must be a string")

    return IngestPayload(
        title=title_val,
        body=body_val,
        group=group_val,
        priority=priority_val,
        tags=list(tags_val),
        url=url_val,
        extras=dict(extras_val),
    )


async def authenticate_ingest_request(
    session: AsyncSession,
    endpoint_id_raw: str,
    ingest_key: str,
) -> AuthenticatedEndpoint:
    tables = await get_tables()
    endpoint_id = _parse_endpoint_id(endpoint_id_raw)

    endpoint_query = select(
        tables.ingest_endpoints.c.id,
        tables.ingest_endpoints.c.user_id,
        tables.ingest_endpoints.c.name,
        tables.ingest_endpoints.c.token_hash,
        tables.ingest_endpoints.c.revoked_at,
        tables.ingest_endpoints.c.deleted_at,
    ).where(tables.ingest_endpoints.c.id == endpoint_id)
    endpoint_result = await session.execute(endpoint_query)
    endpoint = endpoint_result.fetchone()

    if not endpoint:
        raise _auth_error()

    raw_key = ingest_key.strip()
    if not raw_key:
        raise _auth_error()

    token_hash = hash_token(raw_key)
    try:
        if not hmac.compare_digest(token_hash, endpoint.token_hash):
            raise _auth_error()
    except Exception as exc:
        raise _auth_error() from exc

    if endpoint.revoked_at is not None:
        raise _auth_error()

    if endpoint.deleted_at is not None:
        raise _auth_error()

    user_query = select(
        tables.users.c.is_active,
        tables.users.c.email_verified_at,
    ).where(tables.users.c.id == endpoint.user_id)
    user_result = await session.execute(user_query)
    user = user_result.fetchone()

    if not user or not user.is_active:
        raise IngestError(code="forbidden", message="forbidden", status=403)

    if user.email_verified_at is None:
        raise IngestError(
            code="email_not_verified",
            message="email not verified",
            status=403,
        )

    return AuthenticatedEndpoint(
        endpoint_id=endpoint_id,
        user_id=UUID(serialize_uuid(endpoint.user_id)),
    )


async def create_ingest_message(
    session: AsyncSession,
    *,
    endpoint_id: UUID,
    user_id: UUID,
    payload: IngestPayload,
    headers: Mapping[str, str],
    query_params: Mapping[str, str],
    remote_ip: str,
    user_agent: str | None,
    content_type: str | None,
) -> UUID:
    tables = await get_tables()
    now = datetime.now(tz.utc)
    message_id = uuid4()

    await session.execute(
        tables.messages.insert().values(
            id=message_id,
            user_id=user_id,
            ingest_endpoint_id=endpoint_id,
            received_at=now,
            title=payload.title,
            body=payload.body,
            group=payload.group,
            priority=payload.priority,
            tags_json=payload.tags,
            url=_normalized_url(payload.url),
            extras_json=payload.extras,
            content_type=content_type or None,
            body_sha256=hashlib.sha256(payload.body.encode("utf-8")).hexdigest(),
            headers_json=redact_headers(dict(headers)),
            query_json=dict(query_params),
            remote_ip=remote_ip,
            user_agent=user_agent,
            deleted_at=None,
        )
    )

    await session.execute(
        update(tables.ingest_endpoints)
        .where(tables.ingest_endpoints.c.id == endpoint_id)
        .values(last_used_at=now)
    )

    rules_query = select(
        tables.rules.c.id,
        tables.rules.c.filter_json,
        tables.rules.c.channel_id,
    ).where(
        tables.rules.c.user_id == user_id,
        tables.rules.c.enabled.is_(True),
    )
    rules_result = await session.execute(rules_query)
    rules = rules_result.fetchall()

    message_dict = {
        "title": payload.title,
        "body": payload.body,
        "group": payload.group,
        "priority": payload.priority,
        "tags": payload.tags,
        "url": payload.url,
        "extras": payload.extras,
    }

    for rule in rules:
        filter_json = _rule_filter_dict(rule.filter_json)
        if not rule_matches_message(filter_json, message_dict):
            continue

        await session.execute(
            tables.deliveries.insert().values(
                id=uuid4(),
                user_id=user_id,
                message_id=message_id,
                rule_id=UUID(serialize_uuid(rule.id)),
                channel_id=UUID(serialize_uuid(rule.channel_id)),
                status="queued",
                attempt_count=0,
                next_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )

    await session.commit()
    return message_id


__all__ = [
    "IngestError",
    "AuthenticatedEndpoint",
    "IngestPayload",
    "authenticate_ingest_request",
    "create_ingest_message",
    "validate_ingest_payload",
]
