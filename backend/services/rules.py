from __future__ import annotations

import json
from datetime import datetime, timezone as tz
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_tables, serialize_uuid
from ..models import Rule
from .channel_operations import get_channel_record, rule_to_dict
from .channel_records import ChannelRecord
from .channel_validation import require_string_field
from .exceptions import NotFoundError


def _rule_from_row(row: Any) -> Rule:
    filter_json = row.filter_json if isinstance(row.filter_json, dict) else {}
    payload_template = (
        row.payload_template_json if isinstance(row.payload_template_json, dict) else {}
    )

    return Rule(
        id=UUID(serialize_uuid(row.id)),
        name=row.name,
        enabled=row.enabled,
        channel_id=UUID(serialize_uuid(row.channel_id)),
        filter=filter_json,
        payload_template=payload_template,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


async def list_rules(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> list[Rule]:
    tables = await get_tables()

    result = await session.execute(
        select(tables.rules)
        .where(tables.rules.c.user_id == user_id)
        .order_by(tables.rules.c.created_at.desc())
    )

    return [_rule_from_row(row) for row in result.fetchall()]


async def get_rule_detail(
    session: AsyncSession,
    *,
    user_id: UUID,
    rule_id: UUID,
) -> Rule:
    tables = await get_tables()

    result = await session.execute(
        select(tables.rules).where(
            tables.rules.c.id == rule_id.hex,
            tables.rules.c.user_id == user_id,
        )
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("rule_not_found")

    return _rule_from_row(row)


async def _get_rule_record(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> Any:
    tables = await get_tables()

    result = await session.execute(
        select(tables.rules).where(
            tables.rules.c.user_id == user_id,
            tables.rules.c.id == id,
        )
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError()
    return row


async def _get_rule_channel(
    session: AsyncSession,
    *,
    user_id: UUID,
    channel_id: UUID,
) -> ChannelRecord:
    try:
        return await get_channel_record(session, user_id=user_id, id=channel_id)
    except NotFoundError as exc:
        raise NotFoundError("channel not found") from exc


async def create_rule(
    session: AsyncSession,
    *,
    user_id: UUID,
    name: str,
    enabled: bool,
    channel_id: UUID,
    filter_json: dict[str, Any],
    payload_template: dict[str, Any],
) -> dict[str, Any]:
    tables = await get_tables()
    normalized_name = require_string_field({"name": name}, "name")

    rule_id = uuid4()
    now = datetime.now(tz.utc)

    async def _create() -> dict[str, Any]:
        channel = await _get_rule_channel(
            session,
            user_id=user_id,
            channel_id=channel_id,
        )
        await session.execute(
            tables.rules.insert().values(
                id=rule_id,
                user_id=user_id,
                name=normalized_name,
                enabled=bool(enabled),
                filter_json=filter_json,
                created_at=now,
                updated_at=now,
                channel_id=channel.id,
                payload_template_json=payload_template,
            )
        )
        await session.commit()
        rule = await _get_rule_record(session, user_id=user_id, id=rule_id)
        return rule_to_dict(rule)

    return await _create()


async def update_rule(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
    name: str,
    enabled: bool,
    channel_id: UUID,
    filter_json: dict[str, Any],
    payload_template: dict[str, Any],
) -> dict[str, Any]:
    tables = await get_tables()
    normalized_name = require_string_field({"name": name}, "name")

    async def _update() -> dict[str, Any]:
        await _get_rule_record(session, user_id=user_id, id=id)
        channel = await _get_rule_channel(
            session,
            user_id=user_id,
            channel_id=channel_id,
        )
        await session.execute(
            update(tables.rules)
            .where(tables.rules.c.id == id)
            .values(
                name=normalized_name,
                enabled=bool(enabled),
                channel_id=channel.id,
                filter_json=filter_json,
                payload_template_json=payload_template,
                updated_at=datetime.now(tz.utc),
            )
        )
        await session.commit()
        rule = await _get_rule_record(session, user_id=user_id, id=id)
        return rule_to_dict(rule)

    return await _update()


async def delete_rule(
    session: AsyncSession,
    *,
    user_id: UUID,
    id: UUID,
) -> None:
    tables = await get_tables()

    async def _delete() -> None:
        await _get_rule_record(session, user_id=user_id, id=id)
        await session.execute(delete(tables.rules).where(tables.rules.c.id == id))
        await session.commit()

    await _delete()


def _build_preview_message(
    *, ingest_endpoint_id: UUID, ingest_endpoint_name: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "ingest_endpoint_id": str(ingest_endpoint_id),
        "received_at": datetime.now(tz.utc).isoformat(),
        "title": payload.get("title"),
        "body": payload.get("body", ""),
        "group": payload.get("group"),
        "priority": payload.get("priority", 3),
        "tags_json": payload.get("tags", []),
        "url": payload.get("url"),
        "extras_json": payload.get("extras", {}),
        "content_type": "application/json",
        "headers_json": {},
        "query_json": {},
        "remote_ip": "",
    }


async def preview_single_rule(
    session: AsyncSession,
    *,
    user_id: UUID,
    rule_id: UUID,
    ingest_endpoint_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from ..core.rules import rule_matches_message
    from ..core.template import build_template_context, render_template

    tables = await get_tables()

    # Fetch rule with channel
    result = await session.execute(
        select(
            tables.rules.c.filter_json,
            tables.rules.c.payload_template_json,
            tables.channels.c.type,
        )
        .join(tables.channels, tables.rules.c.channel_id == tables.channels.c.id)
        .where(
            tables.rules.c.id == rule_id,
            tables.rules.c.user_id == user_id,
        )
    )
    rule_row = result.fetchone()
    if rule_row is None:
        raise NotFoundError()

    # Fetch ingest endpoint (active only — archived endpoints must 404)
    ep_result = await session.execute(
        select(tables.ingest_endpoints.c.id, tables.ingest_endpoints.c.name).where(
            tables.ingest_endpoints.c.id == ingest_endpoint_id,
            tables.ingest_endpoints.c.user_id == user_id,
            tables.ingest_endpoints.c.revoked_at.is_(None),
            tables.ingest_endpoints.c.deleted_at.is_(None),
        )
    )
    ep_row = ep_result.fetchone()
    if ep_row is None:
        raise NotFoundError()

    message = _build_preview_message(
        ingest_endpoint_id=ingest_endpoint_id,
        ingest_endpoint_name=ep_row.name,
        payload=payload,
    )
    endpoint_dict = {"id": str(ingest_endpoint_id), "name": ep_row.name}

    filter_json = (
        json.loads(rule_row.filter_json)
        if isinstance(rule_row.filter_json, str)
        else (rule_row.filter_json or {})
    )
    template_json = (
        json.loads(rule_row.payload_template_json)
        if isinstance(rule_row.payload_template_json, str)
        else (rule_row.payload_template_json or {})
    )

    matches = rule_matches_message(filter_json, message)
    ctx = build_template_context(message, endpoint_dict)
    rendered = render_template(template_json, ctx)

    return {
        "matches": bool(matches),
        "channel_type": str(rule_row.type),
        "rendered_payload": rendered if isinstance(rendered, dict) else {},
    }


async def preview_all_rules(
    session: AsyncSession,
    *,
    user_id: UUID,
    ingest_endpoint_id: UUID,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from ..core.rules import rule_matches_message
    from ..core.template import build_template_context, render_template

    tables = await get_tables()

    ep_result = await session.execute(
        select(tables.ingest_endpoints.c.id, tables.ingest_endpoints.c.name).where(
            tables.ingest_endpoints.c.id == ingest_endpoint_id,
            tables.ingest_endpoints.c.user_id == user_id,
            tables.ingest_endpoints.c.revoked_at.is_(None),
            tables.ingest_endpoints.c.deleted_at.is_(None),
        )
    )
    ep_row = ep_result.fetchone()
    if ep_row is None:
        raise NotFoundError()

    result = await session.execute(
        select(
            tables.rules,
            tables.channels.c.id.label("ch_id"),
            tables.channels.c.type.label("ch_type"),
            tables.channels.c.name.label("ch_name"),
            tables.channels.c.created_at.label("ch_created_at"),
            tables.channels.c.disabled_at.label("ch_disabled_at"),
        )
        .join(tables.channels, tables.rules.c.channel_id == tables.channels.c.id)
        .where(
            tables.rules.c.user_id == user_id,
            tables.rules.c.enabled.is_(True),
        )
        .order_by(tables.rules.c.created_at.desc())
    )
    rule_rows = result.fetchall()
    total_rules = len(rule_rows)

    message = _build_preview_message(
        ingest_endpoint_id=ingest_endpoint_id,
        ingest_endpoint_name=ep_row.name,
        payload=payload,
    )
    endpoint_dict = {"id": str(ingest_endpoint_id), "name": ep_row.name}
    ctx = build_template_context(message, endpoint_dict)

    matches = []
    for row in rule_rows:
        filter_json = (
            json.loads(row.filter_json)
            if isinstance(row.filter_json, str)
            else (row.filter_json or {})
        )
        if not rule_matches_message(filter_json, message):
            continue
        template_json = (
            json.loads(row.payload_template_json)
            if isinstance(row.payload_template_json, str)
            else (row.payload_template_json or {})
        )
        rendered = render_template(template_json, ctx)
        matches.append(
            {
                "rule": {
                    "id": UUID(serialize_uuid(row.id)),
                    "name": str(row.name),
                    "enabled": bool(row.enabled),
                    "channel_id": UUID(serialize_uuid(row.channel_id)),
                    "filter": filter_json,
                    "payload_template": template_json,
                    "created_at": row.created_at,
                },
                "channel": {
                    "id": UUID(serialize_uuid(row.ch_id)),
                    "type": str(row.ch_type),
                    "name": str(row.ch_name),
                    "created_at": row.ch_created_at,
                    "disabled_at": row.ch_disabled_at,
                },
                "channel_type": str(row.ch_type),
                "rendered_payload": rendered if isinstance(rendered, dict) else {},
            }
        )

    return {
        "matched_count": len(matches),
        "total_rules": total_rules,
        "matches": matches,
    }


__all__ = [
    "list_rules",
    "get_rule_detail",
    "_get_rule_record",
    "_get_rule_channel",
    "create_rule",
    "update_rule",
    "delete_rule",
    "_build_preview_message",
    "preview_single_rule",
    "preview_all_rules",
]
