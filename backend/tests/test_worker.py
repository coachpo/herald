from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

import backend.worker as worker_module
from backend.channel_dispatch import DeliveryError
from backend.store import Store
from backend.worker import Worker


def received(store, **changes):
    message = {'title': '', 'body': 'background delivery', 'priority': 3,
               'target_ids': None, 'idempotency_key': None}
    message.update(changes)
    return store.receive(message)


async def wait_until(task, condition, timeout=2):
    async with asyncio.timeout(timeout):
        while not condition():
            if task.done():
                await task
                raise AssertionError('worker stopped before expected state')
            await asyncio.sleep(0.002)


async def stop(task):
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def run_until(worker, condition):
    task = asyncio.create_task(worker.run())
    try:
        await wait_until(task, condition)
    finally:
        await stop(task)


@pytest.mark.asyncio
async def test_one_target_failure_does_not_cancel_another_targets_delivery(store, target, target_body, settings, monkeypatch):
    other = store.create_target({**target_body, 'name': 'Independent',
                                 'config': {**target_body['config'], 'topic': 'independent'}})
    receipt = received(store)
    calls = []

    async def dispatch(kind, config, message, *, timeout):
        calls.append(config['topic'])
        if config['topic'] == target_body['config']['topic']:
            raise DeliveryError('provider_unavailable')
        return {'http_status': 200}

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, max_attempts=1))
    await run_until(worker, lambda: all(d['status'] in {'failed', 'sent'}
        for d in store.get_message(receipt['message_id'])['deliveries']))
    results = {item['target_id']: item for item in store.get_message(receipt['message_id'])['deliveries']}
    assert results[target['id']]['status'] == 'failed'
    assert results[target['id']]['last_error'] == 'provider_unavailable'
    assert results[other['id']]['status'] == 'sent'
    assert results[other['id']]['last_error'] is None
    assert set(calls) == {target_body['config']['topic'], 'independent'}


@pytest.mark.asyncio
async def test_attempt_timeout_is_bounded_and_does_not_block_sibling_success(store, target, target_body, settings, monkeypatch):
    other = store.create_target({**target_body, 'name': 'Fast',
                                 'config': {**target_body['config'], 'topic': 'fast'}})
    receipt = received(store)
    slow_started = asyncio.Event()
    slow_cancelled = asyncio.Event()

    async def dispatch(kind, config, message, *, timeout):
        if config['topic'] == 'fast':
            return {'http_status': 200}
        slow_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            slow_cancelled.set()

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, delivery_timeout=0.02))
    await run_until(worker, lambda: all(d['status'] in {'retry', 'sent'}
        for d in store.get_message(receipt['message_id'])['deliveries']))
    assert slow_started.is_set()
    assert slow_cancelled.is_set()
    results = {d['target_id']: d for d in store.get_message(receipt['message_id'])['deliveries']}
    assert results[target['id']]['status'] == 'retry'
    assert 'timeout' in results[target['id']]['last_error'].lower()
    assert results[target['id']]['attempts'] == 1
    assert results[other['id']]['status'] == 'sent'


@pytest.mark.asyncio
async def test_concurrency_is_bounded_while_all_targets_eventually_complete(store, target, target_body, settings, monkeypatch):
    for n in range(4):
        store.create_target({**target_body, 'name': f'Target {n}'})
    receipt = received(store)
    active = 0
    peak = 0
    calls = 0
    paired = asyncio.Event()

    async def dispatch(kind, config, message, *, timeout):
        nonlocal active, peak, calls
        active += 1
        peak = max(peak, active)
        calls += 1
        if active == 2:
            paired.set()
        try:
            await paired.wait()
            await asyncio.sleep(0)
            return {'http_status': 200}
        finally:
            active -= 1

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, concurrency=2, delivery_timeout=2))
    await run_until(worker, lambda: all(d['status'] == 'sent'
        for d in store.get_message(receipt['message_id'])['deliveries']))
    assert peak == 2
    assert calls == 5
    assert all(d['attempts'] == 1 for d in store.get_message(receipt['message_id'])['deliveries'])


@pytest.mark.asyncio
async def test_slow_destination_does_not_hold_other_consumers_empty_slots(store, target_body, settings, monkeypatch):
    slow = store.create_target({**target_body, 'name': 'Slow',
                                'config': {**target_body['config'], 'topic': 'slow'}})
    fast = [store.create_target({**target_body, 'name': f'Fast {n}',
                                 'config': {**target_body['config'], 'topic': f'fast-{n}'}})
            for n in range(3)]
    # Force the slow destination to be claimed first; later fast deliveries must
    # all complete through the other slot while the first is still blocked.
    slow_receipt = store.receive({'body': 'slow', 'target_ids': [slow['id']]}, now=100)
    fast_receipt = store.receive({'body': 'fast', 'target_ids': [t['id'] for t in fast]}, now=101)
    slow_started = asyncio.Event()
    release = asyncio.Event()
    fast_calls = []

    async def dispatch(kind, config, message, *, timeout):
        if config['topic'] == 'slow':
            slow_started.set()
            await release.wait()
        else:
            fast_calls.append(config['topic'])
            await asyncio.sleep(0.005)
        return {'http_status': 200}

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, concurrency=2, delivery_timeout=10))
    task = asyncio.create_task(worker.run())
    try:
        await asyncio.wait_for(slow_started.wait(), 1)
        await wait_until(task, lambda: all(d['status'] == 'sent'
            for d in store.get_message(fast_receipt['message_id'])['deliveries']))
        assert len(fast_calls) == 3
        assert not release.is_set()
        assert store.get_message(slow_receipt['message_id'])['deliveries'][0]['status'] == 'sending'
        release.set()
        await wait_until(task, lambda: store.get_message(slow_receipt['message_id'])['deliveries'][0]['status'] == 'sent')
    finally:
        release.set()
        await stop(task)


@pytest.mark.asyncio
async def test_cancellation_leaves_durable_work_recoverable_after_restart(store, target, settings, monkeypatch):
    receipt = received(store)
    sending = asyncio.Event()

    async def dispatch(kind, config, message, *, timeout):
        sending.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, settings)
    task = asyncio.create_task(worker.run())
    await asyncio.wait_for(sending.wait(), 1)
    await stop(task)
    crashed = store.get_message(receipt['message_id'])['deliveries'][0]
    assert crashed['status'] == 'sending'
    assert crashed['attempts'] == 1
    restarted = Store(settings.database_path, settings.encryption_key)
    restarted.initialize()
    assert restarted.recover(max_attempts=settings.max_attempts) == 1
    claimed = restarted.claim(1)
    assert len(claimed) == 1
    assert claimed[0]['id'] == crashed['id']
    restarted.finish(claimed[0]['id'], claimed[0]['lease_token'])
    assert restarted.get_message(receipt['message_id'])['deliveries'][0]['attempts'] == 2


@pytest.mark.asyncio
async def test_worker_run_recovers_crashed_attempt_before_polling(store, target, settings, monkeypatch):
    receipt = received(store)
    old_claim = store.claim(1)[0]
    calls = 0

    async def dispatch(kind, config, message, *, timeout):
        nonlocal calls
        calls += 1
        return {'http_status': 200}

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, settings)
    await run_until(worker, lambda: store.get_message(receipt['message_id'])['deliveries'][0]['status'] == 'sent')
    assert calls == 1
    result = store.get_message(receipt['message_id'])['deliveries'][0]
    assert result['attempts'] == 2
    assert store.finish(old_claim['id'], old_claim['lease_token'], error='stale') is False


@pytest.mark.asyncio
async def test_unexpected_provider_exception_does_not_persist_credentials(store, target, settings, monkeypatch):
    receipt = received(store)
    secret = 'provider-echoed-secret-never-store'

    async def dispatch(kind, config, message, *, timeout):
        raise RuntimeError(secret)

    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, max_attempts=1))
    await run_until(worker, lambda: store.get_message(receipt['message_id'])['deliveries'][0]['status'] == 'failed')
    result = store.get_message(receipt['message_id'])['deliveries'][0]
    assert result['last_error']
    assert secret not in result['last_error']
    assert secret not in str(store.get_message(receipt['message_id']))


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked_operation', ['claim', 'finish'])
async def test_shutdown_waits_for_inflight_transaction_before_releasing_worker(store, target, settings, monkeypatch, blocked_operation):
    import threading

    receipt = received(store)
    started = threading.Event()
    release = threading.Event()
    committed = threading.Event()
    real_operation = getattr(store, blocked_operation)

    def slow_operation(*args, **kwargs):
        started.set()
        assert release.wait(2), 'test failed to release the transaction'
        result = real_operation(*args, **kwargs)
        committed.set()
        return result

    async def dispatch(kind, config, message, *, timeout):
        return {'http_status': 200}

    monkeypatch.setattr(store, blocked_operation, slow_operation)
    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, replace(settings, concurrency=1))
    task = asyncio.create_task(worker.run())
    try:
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done(), 'shutdown returned while a database transaction could still commit'
        assert not committed.is_set()
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done(), 'repeated cancellation detached the transaction thread'
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert committed.is_set()
        status = store.get_message(receipt['message_id'])['deliveries'][0]['status']
        assert status == ('sending' if blocked_operation == 'claim' else 'sent')
    finally:
        release.set()
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_result_commit_failure_does_not_cancel_sibling_and_stops_the_worker(store, target_body, settings, monkeypatch):
    import sqlite3

    first = store.create_target({**target_body, 'name': 'First'})
    other = store.create_target({**target_body, 'name': 'Independent',
                                 'config': {**target_body['config'], 'topic': 'independent'}})
    first_receipt = store.receive({'body': 'first', 'target_ids': [first['id']]}, now=100)
    sibling_receipt = store.receive({'body': 'sibling', 'target_ids': [other['id']]}, now=101)
    failing_id = store.get_message(first_receipt['message_id'])['deliveries'][0]['id']
    real_finish = store.finish
    sibling_started = asyncio.Event()
    sibling_finished = asyncio.Event()

    def finish(delivery_id, *args, **kwargs):
        if delivery_id == failing_id:
            raise sqlite3.OperationalError('simulated result commit failure')
        return real_finish(delivery_id, *args, **kwargs)

    async def dispatch(kind, config, message, *, timeout):
        if config['topic'] == 'independent':
            sibling_started.set()
            await asyncio.sleep(0.02)
            sibling_finished.set()
        else:
            await sibling_started.wait()
        return {'http_status': 200}

    monkeypatch.setattr(store, 'finish', finish)
    monkeypatch.setattr(worker_module, 'dispatch', dispatch)
    worker = Worker(store, settings)
    with pytest.raises(RuntimeError, match='delivery_worker_stopped'):
        await asyncio.wait_for(worker.run(), 1)
    assert sibling_finished.is_set()
    assert store.get_message(first_receipt['message_id'])['deliveries'][0]['status'] == 'sending'
    assert store.get_message(sibling_receipt['message_id'])['deliveries'][0]['status'] == 'sent'
