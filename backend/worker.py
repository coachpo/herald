"""Independent, bounded delivery consumers; network effects hold no DB locks."""
from __future__ import annotations

import asyncio
import logging

from .channel_dispatch import DeliveryError, dispatch
from .tasks import database_call

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    async def _deliver(self, delivery):
        error = None
        try:
            async with asyncio.timeout(self.settings.delivery_timeout):
                await dispatch(delivery['kind'], delivery['config'], delivery['message'],
                               timeout=self.settings.delivery_timeout)
        except TimeoutError:
            error = 'timeout'
        except DeliveryError as exc:
            error = exc.code
        except Exception:
            # Transport exception strings can contain credentials or payloads.
            error = 'transport_error'
        # Cancellation leaves sending durable for recovery. If saving this result
        # fails, stop claiming new work and expose degraded worker health.
        await database_call(self.store.finish, delivery['id'], delivery['lease_token'],
                            error=error, max_attempts=self.settings.max_attempts,
                            backoff_base_seconds=self.settings.backoff_base_seconds,
                            backoff_max_seconds=self.settings.backoff_max_seconds)

    async def _consume(self, stopping):
        try:
            while not stopping.is_set():
                deliveries = await database_call(self.store.claim, 1,
                                                  max_attempts=self.settings.max_attempts)
                if stopping.is_set():
                    # Another consumer lost a result commit while this claim was
                    # in flight. Retain the claimed task for restart recovery.
                    return
                if deliveries:
                    await self._deliver(deliveries[0])
                else:
                    await asyncio.sleep(self.settings.poll_seconds)
        except asyncio.CancelledError:
            stopping.set()
            raise
        except Exception as exc:
            logger.error('delivery worker stopped (%s)', type(exc).__name__)
            stopping.set()
            raise RuntimeError('delivery_worker_stopped') from None

    async def run(self) -> None:
        try:
            await database_call(self.store.recover, max_attempts=self.settings.max_attempts)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error('delivery recovery failed (%s)', type(exc).__name__)
            raise RuntimeError('delivery_worker_stopped') from None
        stopping = asyncio.Event()
        tasks = [asyncio.create_task(self._consume(stopping))
                 for _ in range(self.settings.concurrency)]
        group = asyncio.gather(*tasks, return_exceptions=True)
        try:
            results = await asyncio.shield(group)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
            # Repeated shutdown requests must not release the singleton lock
            # before a consumer's in-flight SQLite transaction has settled.
            while not group.done():
                try:
                    await asyncio.shield(group)
                except asyncio.CancelledError:
                    continue
            raise
        if any(isinstance(result, BaseException) for result in results):
            raise RuntimeError('delivery_worker_stopped') from None
