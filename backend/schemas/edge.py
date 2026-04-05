from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class EdgeIngestEndpoint(BaseModel):
    id: UUID
    name: str
    token_hash: str


class EdgeChannel(BaseModel):
    id: UUID
    type: str
    name: str
    config: dict[str, Any]


class EdgeRule(BaseModel):
    id: UUID
    name: str
    filter: dict[str, Any]
    channel_id: UUID
    payload_template: dict[str, Any]


class EdgeConfigResponse(BaseModel):
    ingest_endpoints: list[EdgeIngestEndpoint]
    channels: list[EdgeChannel]
    rules: list[EdgeRule]
    updated_at: datetime
    version: str


__all__ = [
    "EdgeChannel",
    "EdgeConfigResponse",
    "EdgeIngestEndpoint",
    "EdgeRule",
]
