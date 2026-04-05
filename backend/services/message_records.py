from __future__ import annotations

from typing import Any
from uuid import UUID

from ..database import serialize_uuid
from ..models import Delivery, DeliveryCounters, MessageDetail, MessageSummary


def message_summary_from_row(
    row: Any,
    *,
    deliveries: DeliveryCounters,
) -> MessageSummary:
    tags = row.tags_json if isinstance(row.tags_json, list) else []
    return MessageSummary(
        id=UUID(serialize_uuid(row.id)),
        ingest_endpoint_id=UUID(serialize_uuid(row.ingest_endpoint_id)),
        received_at=row.received_at,
        title=row.title,
        body_preview=(row.body or "")[:200],
        group=row.group,
        priority=row.priority,
        tags=tags,
        deliveries=deliveries,
    )


def message_detail_from_row(row: Any) -> MessageDetail:
    tags = row.tags_json if isinstance(row.tags_json, list) else []
    extras = row.extras_json if isinstance(row.extras_json, dict) else {}
    headers = row.headers_json if isinstance(row.headers_json, dict) else {}
    query_params = row.query_json if isinstance(row.query_json, dict) else {}

    return MessageDetail(
        id=UUID(serialize_uuid(row.id)),
        ingest_endpoint_id=UUID(serialize_uuid(row.ingest_endpoint_id)),
        received_at=row.received_at,
        title=row.title,
        body=row.body or "",
        group=row.group,
        priority=row.priority,
        tags=tags,
        url=row.url,
        extras=extras,
        content_type=row.content_type,
        headers=headers,
        query=query_params,
        remote_ip=row.remote_ip or "",
        user_agent=row.user_agent,
        deleted_at=row.deleted_at,
    )


def delivery_from_row(row: Any) -> Delivery:
    provider_response = (
        row.provider_response_json
        if isinstance(row.provider_response_json, dict)
        else {}
    )
    return Delivery(
        id=UUID(serialize_uuid(row.id)),
        message_id=UUID(serialize_uuid(row.message_id)),
        rule_id=UUID(serialize_uuid(row.rule_id)),
        rule_name=row.rule_name,
        channel_id=UUID(serialize_uuid(row.channel_id)),
        channel_name=row.channel_name,
        status=row.status,
        attempt_count=row.attempt_count,
        next_attempt_at=row.next_attempt_at,
        sent_at=row.sent_at,
        last_error=row.last_error,
        provider_response=provider_response,
    )


__all__ = [
    "delivery_from_row",
    "message_detail_from_row",
    "message_summary_from_row",
]
