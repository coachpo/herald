"""Wait for SQLite transaction threads before an owning task can shut down."""
from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def database_call(operation, *args, **kwargs):
    # Cancelling to_thread alone does not stop its thread. A caller must retain
    # the singleton process lock until the in-flight transaction has settled.
    task = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # Repeated shutdown/cancellation requests must not detach the write.
                continue
            except Exception:
                break
        try:
            task.result()
        except Exception as exc:
            logger.error('database operation failed during shutdown (%s)', type(exc).__name__)
        raise
