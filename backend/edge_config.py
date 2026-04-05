from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .core.crypto import decrypt_json_bytes
from .database import get_tables, serialize_uuid


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str) and value:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _decrypt_channel_config(ciphertext: str) -> dict[str, Any]:
    payload = decrypt_json_bytes(ciphertext).decode("utf-8")
    parsed = json.loads(payload)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("invalid_channel_config")


async def build_edge_config(
    *, session: AsyncSession, user_id: uuid.UUID
) -> dict[str, Any]:
    tables = await get_tables()

    ingest_rows = (
        await session.execute(
            select(
                tables.ingest_endpoints.c.id,
                tables.ingest_endpoints.c.name,
                tables.ingest_endpoints.c.token_hash,
            )
            .where(
                and_(
                    tables.ingest_endpoints.c.user_id == user_id,
                    tables.ingest_endpoints.c.revoked_at.is_(None),
                    tables.ingest_endpoints.c.deleted_at.is_(None),
                )
            )
            .order_by(tables.ingest_endpoints.c.id)
        )
    ).all()

    channel_rows = (
        await session.execute(
            select(
                tables.channels.c.id,
                tables.channels.c.type,
                tables.channels.c.name,
                tables.channels.c.config_json_encrypted,
            )
            .where(
                and_(
                    tables.channels.c.user_id == user_id,
                    tables.channels.c.disabled_at.is_(None),
                    tables.channels.c.type.in_(("bark", "ntfy")),
                )
            )
            .order_by(tables.channels.c.id)
        )
    ).all()

    rule_rows = (
        await session.execute(
            select(
                tables.rules.c.id,
                tables.rules.c.name,
                tables.rules.c.filter_json,
                tables.rules.c.channel_id,
                tables.rules.c.payload_template_json,
            )
            .join(tables.channels, tables.rules.c.channel_id == tables.channels.c.id)
            .where(
                and_(
                    tables.rules.c.user_id == user_id,
                    tables.rules.c.enabled.is_(True),
                    tables.channels.c.disabled_at.is_(None),
                    tables.channels.c.type.in_(("bark", "ntfy")),
                )
            )
            .order_by(tables.rules.c.id)
        )
    ).all()

    config: dict[str, Any] = {
        "ingest_endpoints": [
            {
                "id": serialize_uuid(row.id),
                "name": str(row.name),
                "token_hash": str(row.token_hash),
            }
            for row in ingest_rows
        ],
        "channels": [
            {
                "id": serialize_uuid(row.id),
                "type": str(row.type),
                "name": str(row.name),
                "config": _decrypt_channel_config(str(row.config_json_encrypted)),
            }
            for row in channel_rows
        ],
        "rules": [
            {
                "id": serialize_uuid(row.id),
                "name": str(row.name),
                "filter": _json_object(row.filter_json),
                "channel_id": serialize_uuid(row.channel_id),
                "payload_template": _json_object(row.payload_template_json),
            }
            for row in rule_rows
        ],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    version_payload = {
        "ingest_endpoints": config["ingest_endpoints"],
        "channels": config["channels"],
        "rules": config["rules"],
    }
    config_bytes = json.dumps(
        version_payload, separators=(",", ":"), sort_keys=True
    ).encode()
    config["version"] = sha256(config_bytes).hexdigest()[:16]
    return config
