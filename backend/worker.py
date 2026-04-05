import asyncio
import signal
from datetime import datetime, timedelta, timezone as tz
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .channel_dispatch import dispatch_channel_message
from .config import get_settings
from .database import get_session, get_tables
from .logging_config import setup_logging

logger = structlog.get_logger(__name__)

_shutdown_requested = False


def _backoff_seconds(attempt_count: int) -> int:
    settings = get_settings()
    base = settings.delivery_backoff_base_seconds
    max_delay = settings.delivery_backoff_max_seconds
    delay = base * (2 ** max(attempt_count - 1, 0))
    return min(max_delay, delay)


def _signal_handler(signum: int, frame: Any) -> None:
    global _shutdown_requested
    logger.info("shutdown_signal_received", signal=signum)
    _shutdown_requested = True


async def claim_due_deliveries(
    session: AsyncSession,
    *,
    now: datetime,
    batch_size: int,
) -> list[Any]:
    tables = await get_tables()

    query = (
        select(
            tables.deliveries.c.id,
            tables.deliveries.c.user_id,
            tables.deliveries.c.message_id,
            tables.deliveries.c.rule_id,
            tables.deliveries.c.channel_id,
            tables.deliveries.c.status,
            tables.deliveries.c.attempt_count,
            tables.deliveries.c.next_attempt_at,
            tables.deliveries.c.last_error,
        )
        .where(
            tables.deliveries.c.status.in_(["queued", "retry"]),
            tables.deliveries.c.next_attempt_at <= now,
        )
        .order_by(tables.deliveries.c.next_attempt_at)
        .limit(batch_size)
    )

    query = query.with_for_update(skip_locked=True)

    result = await session.execute(query)
    deliveries = list(result.fetchall())

    if not deliveries:
        return []

    delivery_ids = [d.id for d in deliveries]

    await session.execute(
        update(tables.deliveries)
        .where(tables.deliveries.c.id.in_(delivery_ids))
        .values(status="sending", updated_at=now)
    )
    await session.commit()

    return deliveries


async def process_delivery(
    session: AsyncSession,
    delivery: Any,
) -> None:
    tables = await get_tables()
    settings = get_settings()
    max_attempts = settings.delivery_max_attempts
    now = datetime.now(tz.utc)

    try:
        rule_query = select(
            tables.rules.c.enabled,
            tables.rules.c.filter_json,
            tables.rules.c.payload_template_json,
        ).where(tables.rules.c.id == delivery.rule_id)
        rule_result = await session.execute(rule_query)
        rule = rule_result.fetchone()

        if not rule or not rule.enabled:
            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="failed",
                    last_error="rule_disabled",
                    updated_at=now,
                )
            )
            await session.commit()
            return

        channel_query = select(
            tables.channels.c.type,
            tables.channels.c.config_json_encrypted,
            tables.channels.c.disabled_at,
        ).where(tables.channels.c.id == delivery.channel_id)
        channel_result = await session.execute(channel_query)
        channel = channel_result.fetchone()

        if not channel or channel.disabled_at is not None:
            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="failed",
                    last_error="channel_disabled",
                    updated_at=now,
                )
            )
            await session.commit()
            return

        message_query = select(
            tables.messages.c.title,
            tables.messages.c.body,
            tables.messages.c.group,
            tables.messages.c.priority,
            tables.messages.c.tags_json,
            tables.messages.c.url,
            tables.messages.c.extras_json,
            tables.messages.c.ingest_endpoint_id,
        ).where(tables.messages.c.id == delivery.message_id)
        message_result = await session.execute(message_query)
        message = message_result.fetchone()

        if not message:
            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="failed",
                    last_error="message_not_found",
                    updated_at=now,
                )
            )
            await session.commit()
            return

        endpoint_query = select(tables.ingest_endpoints.c.name).where(
            tables.ingest_endpoints.c.id == message.ingest_endpoint_id
        )
        endpoint_result = await session.execute(endpoint_query)
        endpoint = endpoint_result.fetchone()

        from .core.crypto import decrypt_json_bytes
        import json

        config = json.loads(
            decrypt_json_bytes(str(channel.config_json_encrypted)).decode("utf-8")
        )

        message_dict = {
            "title": message.title,
            "body": message.body,
            "group": message.group,
            "priority": message.priority,
            "tags": message.tags_json if isinstance(message.tags_json, list) else [],
            "url": message.url,
            "extras": message.extras_json
            if isinstance(message.extras_json, dict)
            else {},
        }

        ingest_endpoint_dict = {"name": endpoint.name if endpoint else "unknown"}

        channel_type = str(channel.type).strip()
        ok, meta = await dispatch_channel_message(
            channel_type=channel_type,
            config=config,
            payload_template=rule.payload_template_json
            if isinstance(rule.payload_template_json, dict)
            else {},
            message=message_dict,
            ingest_endpoint=ingest_endpoint_dict,
        )

        if ok:
            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="sent",
                    sent_at=now,
                    provider_response_json=meta,
                    updated_at=now,
                )
            )
            await session.commit()
            logger.info(
                "delivery_sent",
                delivery_id=str(delivery.id),
                channel_type=channel_type,
            )
        else:
            raise Exception(f"provider_failed: {meta}")

    except Exception as exc:
        attempt_count = delivery.attempt_count + 1
        error_msg = str(exc)[:500]

        if attempt_count >= max_attempts:
            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="failed",
                    attempt_count=attempt_count,
                    last_error=error_msg,
                    updated_at=now,
                )
            )
            logger.warning(
                "delivery_failed_permanently",
                delivery_id=str(delivery.id),
                attempt_count=attempt_count,
                error=error_msg,
            )
        else:
            backoff = _backoff_seconds(attempt_count)
            next_attempt = now + timedelta(seconds=backoff)

            await session.execute(
                update(tables.deliveries)
                .where(tables.deliveries.c.id == delivery.id)
                .values(
                    status="retry",
                    attempt_count=attempt_count,
                    next_attempt_at=next_attempt,
                    last_error=error_msg,
                    updated_at=now,
                )
            )
            logger.info(
                "delivery_retry_scheduled",
                delivery_id=str(delivery.id),
                attempt_count=attempt_count,
                backoff_seconds=backoff,
                error=error_msg,
            )

        await session.commit()


async def process_delivery_batch() -> None:
    settings = get_settings()
    batch_size = settings.worker_batch_size
    now = datetime.now(tz.utc)

    async for session in get_session():
        deliveries = await claim_due_deliveries(
            session,
            now=now,
            batch_size=batch_size,
        )

        if not deliveries:
            break

        tasks = [process_delivery(session, d) for d in deliveries]
        await asyncio.gather(*tasks, return_exceptions=True)
        break


async def delivery_worker() -> None:
    global _shutdown_requested

    setup_logging()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    settings = get_settings()
    poll_seconds = settings.worker_poll_seconds

    logger.info("delivery_worker_started")

    while not _shutdown_requested:
        try:
            await process_delivery_batch()
            await asyncio.sleep(poll_seconds)
        except Exception as exc:
            logger.exception("worker_error", error=str(exc))
            await asyncio.sleep(5)

    logger.info("delivery_worker_stopped")


if __name__ == "__main__":
    asyncio.run(delivery_worker())
