from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BatchDeleteMessagesRequest(BaseModel):
    older_than_days: int = Field(ge=1)
    ingest_endpoint_id: UUID | None = None


class BatchDeleteMessagesResponse(BaseModel):
    deleted_count: int


class DeliveryCounters(BaseModel):
    queued: int = 0
    sending: int = 0
    retry: int = 0
    sent: int = 0
    failed: int = 0


class MessageSummary(BaseModel):
    id: UUID
    ingest_endpoint_id: UUID
    received_at: datetime
    title: str | None
    body_preview: str
    group: str | None
    priority: int
    tags: list[str]
    deliveries: DeliveryCounters

    class Config:
        from_attributes = True


class MessageDetail(BaseModel):
    id: UUID
    ingest_endpoint_id: UUID
    received_at: datetime
    title: str | None
    body: str
    group: str | None
    priority: int
    tags: list[str]
    url: str | None
    extras: dict[str, Any]
    content_type: str | None
    headers: dict[str, Any]
    query: dict[str, Any]
    remote_ip: str
    user_agent: str | None
    deleted_at: datetime | None

    class Config:
        from_attributes = True


class Delivery(BaseModel):
    id: UUID
    message_id: UUID
    rule_id: UUID
    rule_name: str | None
    channel_id: UUID
    channel_name: str | None
    status: str
    attempt_count: int
    next_attempt_at: datetime | None
    sent_at: datetime | None
    last_error: str | None
    provider_response: dict[str, Any]

    class Config:
        from_attributes = True


class MessagesResponse(BaseModel):
    messages: list[MessageSummary]


class MessageResponse(BaseModel):
    message: MessageDetail


class DeliveriesResponse(BaseModel):
    deliveries: list[Delivery]


__all__ = [
    "BatchDeleteMessagesRequest",
    "BatchDeleteMessagesResponse",
    "DeliveriesResponse",
    "Delivery",
    "DeliveryCounters",
    "MessageDetail",
    "MessageResponse",
    "MessageSummary",
    "MessagesResponse",
]
