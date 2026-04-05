from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from ..core.crypto import decrypt_json_bytes, encrypt_json_bytes
from ..database import serialize_uuid


@dataclass
class ChannelRecord:
    id: UUID
    type: str
    name: str
    created_at: datetime
    disabled_at: datetime | None
    config_json_encrypted: str

    @property
    def config(self) -> dict[str, Any]:
        payload = decrypt_json_bytes(self.config_json_encrypted).decode("utf-8")
        parsed = json.loads(payload)
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("invalid_channel_config")

    @config.setter
    def config(self, config: dict[str, Any]) -> None:
        raw = json.dumps(config, separators=(",", ":")).encode("utf-8")
        self.config_json_encrypted = encrypt_json_bytes(raw)


def channel_to_dict(channel: ChannelRecord) -> dict[str, Any]:
    return {
        "id": channel.id,
        "type": channel.type,
        "name": channel.name,
        "created_at": channel.created_at,
        "disabled_at": channel.disabled_at,
        "config": channel.config,
    }


def channel_from_row(row: Any) -> ChannelRecord:
    return ChannelRecord(
        id=UUID(serialize_uuid(row.id)),
        type=str(row.type),
        name=str(row.name),
        created_at=row.created_at,
        disabled_at=row.disabled_at,
        config_json_encrypted=str(row.config_json_encrypted),
    )


__all__ = ["ChannelRecord", "channel_from_row", "channel_to_dict"]
