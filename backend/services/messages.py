from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_tables
from ..models import (
    Delivery,
    DeliveryCounters,
    MessageDetail,
    MessageSummary,
)
from .exceptions import NotFoundError
from .message_records import (
    delivery_from_row,
    message_detail_from_row,
    message_summary_from_row,
)


def _parse_datetime_filter(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def list_messages(
    session: AsyncSession,
    *,
    user_id: UUID,
    ingest_endpoint_id: UUID | None,
    priority_min: int | None,
    priority_max: int | None,
    from_: str | None,
    to: str | None,
) -> list[MessageSummary]:
    tables = await get_tables()

    query = (
        select(tables.messages)
        .where(tables.messages.c.user_id == user_id)
        .where(tables.messages.c.deleted_at.is_(None))
        .order_by(tables.messages.c.received_at.desc())
        .limit(500)
    )

    if ingest_endpoint_id:
        query = query.where(
            tables.messages.c.ingest_endpoint_id == ingest_endpoint_id.hex
        )

    if priority_min is not None and isinstance(priority_min, int):
        query = query.where(tables.messages.c.priority >= priority_min)

    if priority_max is not None and isinstance(priority_max, int):
        query = query.where(tables.messages.c.priority <= priority_max)

    from_dt = _parse_datetime_filter(from_)
    if from_dt is not None:
        query = query.where(tables.messages.c.received_at >= from_dt)

    to_dt = _parse_datetime_filter(to)
    if to_dt is not None:
        query = query.where(tables.messages.c.received_at <= to_dt)

    result = await session.execute(query)
    message_rows = result.fetchall()

    delivery_counts: dict[Any, DeliveryCounters] = {}
    message_ids = [row.id for row in message_rows]
    if message_ids:
        count_result = await session.execute(
            select(
                tables.deliveries.c.message_id,
                tables.deliveries.c.status,
                func.count().label("delivery_count"),
            )
            .where(tables.deliveries.c.message_id.in_(message_ids))
            .group_by(tables.deliveries.c.message_id, tables.deliveries.c.status)
        )

        for row in count_result:
            counters = delivery_counts.setdefault(row.message_id, DeliveryCounters())
            if row.status == "queued":
                counters.queued = row.delivery_count
            elif row.status == "sending":
                counters.sending = row.delivery_count
            elif row.status == "retry":
                counters.retry = row.delivery_count
            elif row.status == "sent":
                counters.sent = row.delivery_count
            elif row.status == "failed":
                counters.failed = row.delivery_count

    return [
        message_summary_from_row(
            row,
            deliveries=delivery_counts.get(row.id, DeliveryCounters()),
        )
        for row in message_rows
    ]


async def get_message_detail(
    session: AsyncSession,
    *,
    user_id: UUID,
    message_id: UUID,
) -> MessageDetail:
    tables = await get_tables()
    result = await session.execute(
        select(tables.messages).where(
            tables.messages.c.id == message_id.hex,
            tables.messages.c.user_id == user_id,
        )
    )
    row = result.fetchone()
    if row is None:
        raise NotFoundError("message_not_found")

    return message_detail_from_row(row)


async def get_message_deliveries(
    session: AsyncSession,
    *,
    user_id: UUID,
    message_id: UUID,
) -> list[Delivery]:
    tables = await get_tables()

    ownership_result = await session.execute(
        select(tables.messages.c.id).where(
            tables.messages.c.id == message_id.hex,
            tables.messages.c.user_id == user_id,
        )
    )
    if ownership_result.fetchone() is None:
        raise NotFoundError("message_not_found")

    result = await session.execute(
        select(
            tables.deliveries,
            tables.rules.c.name.label("rule_name"),
            tables.channels.c.name.label("channel_name"),
        )
        .outerjoin(tables.rules, tables.deliveries.c.rule_id == tables.rules.c.id)
        .outerjoin(
            tables.channels, tables.deliveries.c.channel_id == tables.channels.c.id
        )
        .where(tables.deliveries.c.message_id == message_id.hex)
        .order_by(tables.deliveries.c.created_at.desc())
    )

    return [delivery_from_row(row) for row in result.fetchall()]


async def delete_message(
    session: AsyncSession,
    *,
    user_id: UUID,
    message_id: UUID,
) -> None:
    from datetime import datetime, timezone as tz

    tables = await get_tables()
    now = datetime.now(tz.utc)

    result = await session.execute(
        update(tables.messages)
        .where(
            tables.messages.c.user_id == user_id,
            tables.messages.c.id == message_id,
            tables.messages.c.deleted_at.is_(None),
        )
        .values(deleted_at=now)
    )

    updated = int(cast(Any, result).rowcount or 0)
    if not updated:
        raise NotFoundError()

    await session.commit()


async def batch_delete_messages(
    session: AsyncSession,
    *,
    user_id: UUID,
    older_than_days: int,
    ingest_endpoint_id: UUID | None,
) -> int:
    from datetime import datetime, timedelta, timezone as tz

    tables = await get_tables()

    cutoff = datetime.now(tz.utc) - timedelta(days=older_than_days)
    now = datetime.now(tz.utc)

    query = (
        update(tables.messages)
        .where(
            tables.messages.c.user_id == user_id,
            tables.messages.c.deleted_at.is_(None),
            tables.messages.c.received_at < cutoff,
        )
        .values(deleted_at=now)
    )

    if ingest_endpoint_id:
        query = query.where(tables.messages.c.ingest_endpoint_id == ingest_endpoint_id)

    result = await session.execute(query)
    await session.commit()

    return int(cast(Any, result).rowcount or 0)


__all__ = [
    "list_messages",
    "get_message_detail",
    "get_message_deliveries",
    "delete_message",
    "batch_delete_messages",
]
