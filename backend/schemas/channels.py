from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ChannelCreateRequest(BaseModel):
    type: str
    name: str = Field(min_length=1, max_length=200)
    config: dict[str, Any]


class ChannelTestRequest(BaseModel):
    title: str | None = None
    body: str | None = None
    payload_json: dict[str, Any] | None = None


class Channel(BaseModel):
    id: UUID
    type: str
    name: str
    created_at: datetime
    disabled_at: datetime | None

    class Config:
        from_attributes = True


class ChannelsResponse(BaseModel):
    channels: list[Channel]


class ChannelWithConfigResponse(BaseModel):
    channel: Channel
    config: dict[str, Any]


class ChannelTestResponse(BaseModel):
    ok: bool
    channel_id: str
    channel_type: str
    provider_response: dict[str, Any]


__all__ = [
    "Channel",
    "ChannelCreateRequest",
    "ChannelTestRequest",
    "ChannelTestResponse",
    "ChannelWithConfigResponse",
    "ChannelsResponse",
]
