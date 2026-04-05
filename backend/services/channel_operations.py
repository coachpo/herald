from __future__ import annotations

from datetime import datetime, timezone as tz
from typing import Any, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..channel_dispatch import dispatch_channel_message
from ..database import get_tables, serialize_uuid
from ..models import Channel
from .channel_records import ChannelRecord, channel_from_row, channel_to_dict
from .channel_validation import (
    _normalize_channel_config,
    normalize_channel_type,
    require_string_field,
)
from .exceptions import NotFoundError, _json_object


def rule_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": UUID(serialize_uuid(row.id)),
        "name": str(row.name),
        "enabled": bool(row.enabled),
        "channel_id": UUID(serialize_uuid(row.channel_id)),
        "filter": _json_object(row.filter_json),
        "payload_template": _json_object(row.payload_template_json),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _channel_summary_from_row(row: Any) -> Channel:
    return Channel(
        id=UUID(serialize_uuid(row.id)),
        type=str(row.type),
        name=str(row.name),
        created_at=row.created_at,
        disabled_at=row.disabled_at,
    )


async def list_channels(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> list[Channel]:
    tables = await get_tables()
    result = await session.execute(
        select(tables.channels)
        .where(tables.channels.c.user_id == user_id)
        .order_by(tables.channels.c.created_at.desc())
    )
    return [_channel_summary_from_row(row) for row in result.fetchall()]


async def get_channel_record(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> ChannelRecord:
    tables = await get_tables()
    result = await session.execute(
        select(tables.channels).where(
            tables.channels.c.user_id == user_id,
            tables.channels.c.id == id,
        )
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError()
    return channel_from_row(row)


async def create_channel(
    session: AsyncSession,
    *,
    user_id: UUID,
    type: str,
    name: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    tables = await get_tables()
    normalized_type = normalize_channel_type(type)
    normalized_name = require_string_field({"name": name}, "name")
    normalized_config = _normalize_channel_config(normalized_type, config)
    channel_id = uuid4()
    created_at = datetime.now(tz.utc)

    pending = ChannelRecord(
        id=channel_id,
        type=normalized_type,
        name=normalized_name,
        created_at=created_at,
        disabled_at=None,
        config_json_encrypted="",
    )
    pending.config = normalized_config
    await session.execute(
        tables.channels.insert().values(
            id=channel_id,
            user_id=user_id,
            type=normalized_type,
            name=normalized_name,
            config_json_encrypted=pending.config_json_encrypted,
            created_at=created_at,
            disabled_at=None,
        )
    )
    await session.commit()
    return channel_to_dict(pending)


async def delete_channel(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> None:
    tables = await get_tables()
    result = await session.execute(
        delete(tables.channels).where(
            tables.channels.c.user_id == user_id,
            tables.channels.c.id == id,
        )
    )
    deleted = int(cast(Any, result).rowcount or 0)
    if not deleted:
        await session.rollback()
        raise NotFoundError()
    await session.commit()


async def test_channel(
    session: AsyncSession,
    *,
    user_id: UUID,
    channel_id: UUID,
    title: str | None,
    body: str | None,
    payload_json: dict[str, Any] | None,
) -> dict[str, Any]:
    channel = await get_channel_record(session, user_id=user_id, id=channel_id)
    channel_dict = channel_to_dict(channel)
    channel_type = channel_dict["type"]
    config = channel_dict["config"]

    test_payload = payload_json or {}
    test_payload.setdefault("title", title or "Test")
    test_payload.setdefault("body", body or "Test message")

    ok, meta = await dispatch_channel_message(
        channel_type=channel_type,
        config=config,
        payload_template={},
        message=test_payload,
        ingest_endpoint={"name": "test"},
    )

    provider_response = dict(meta)
    provider_response.setdefault("provider", channel_type)
    return {
        "ok": bool(ok),
        "channel_id": str(channel_id),
        "channel_type": channel_type,
        "provider_response": provider_response,
    }


__all__ = [
    "create_channel",
    "delete_channel",
    "get_channel_record",
    "list_channels",
    "rule_to_dict",
    "test_channel",
]
