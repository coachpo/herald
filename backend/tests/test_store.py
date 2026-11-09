from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from backend.store import Store


def payload(**changes):
    result = {'title': 'Stored message', 'body': 'durable body', 'priority': 3,
              'target_ids': None, 'idempotency_key': None}
    result.update(changes)
    return result


def make_target(store, target_body, **changes):
    return store.create_target({**target_body, **changes})


def test_store_is_wal_and_reinitialization_preserves_committed_receipts(store, settings, target_body):
    make_target(store, target_body)
    receipt = store.receive(payload())
    reopened = Store(settings.database_path, settings.encryption_key)
    reopened.initialize()
    assert reopened.get_message(receipt['message_id'])['body'] == 'durable body'
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('PRAGMA journal_mode').fetchone()[0].lower() == 'wal'
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 1


def test_concurrent_retransmissions_create_one_receipt_and_one_target_delivery(store, target_body, settings):
    target = make_target(store, target_body)
    request = payload(idempotency_key='concurrent-client-receipt', target_ids=[target['id']])
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(lambda _: store.receive(request), range(16)))
    assert len({r['message_id'] for r in receipts}) == 1
    assert sum(not r['duplicate'] for r in receipts) == 1
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 1
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 1


def test_failure_halfway_through_fanout_rolls_back_entire_receipt(store, target_body, settings):
    make_target(store, target_body)
    make_target(store, target_body, name='Secondary')
    with sqlite3.connect(settings.database_path) as db:
        db.execute("""CREATE TRIGGER fail_second_delivery BEFORE INSERT ON deliveries
            WHEN (SELECT COUNT(*) FROM deliveries) = 1
            BEGIN SELECT RAISE(ABORT, 'simulated full disk'); END""")
    with pytest.raises(sqlite3.Error):
        store.receive(payload())
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 0


def test_duplicate_receipt_survives_current_target_becoming_disabled(store, target_body):
    target = make_target(store, target_body)
    original = store.receive(payload(idempotency_key='stable-receipt'))
    store.update_target(target['id'], {**target_body, 'enabled': False})
    repeated = store.receive(payload(idempotency_key='stable-receipt'))
    assert repeated == {'message_id': original['message_id'], 'duplicate': True}
    message = store.get_message(original['message_id'])
    assert len(message['deliveries']) == 1
    assert message['deliveries'][0]['target_id'] == target['id']


def test_duplicate_does_not_add_new_default_targets_to_an_already_accepted_message(store, target_body):
    first_target = make_target(store, target_body)
    first = store.receive(payload(idempotency_key='fixed-destination-set'))
    make_target(store, target_body, name='Later default')
    duplicate = store.receive(payload(idempotency_key='fixed-destination-set'))
    assert duplicate['message_id'] == first['message_id']
    assert duplicate['duplicate'] is True
    assert {d['target_id'] for d in store.get_message(first['message_id'])['deliveries']} == {first_target['id']}


def test_provider_config_is_encrypted_in_all_retained_sqlite_files(store, target_body, settings):
    make_target(store, target_body)
    secret = target_body['config']['access_token'].encode()
    # Check the WAL as well: scanning only the main file could miss plaintext writes.
    for path in settings.data_dir.glob('herald.sqlite3*'):
        assert secret not in path.read_bytes()


def test_concurrent_claims_cannot_send_the_same_delivery_twice(store, target):
    receipt = store.receive(payload(), now=100)
    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(lambda _: store.claim(1, now=100), range(16)))
    claimed = [item for batch in batches for item in batch]
    assert len(claimed) == 1
    message = store.get_message(receipt['message_id'])
    assert message['deliveries'][0]['status'] == 'sending'
    assert message['deliveries'][0]['attempts'] == 1


def test_recovery_reclaims_unfinished_work_and_fences_stale_completion(store, target):
    receipt = store.receive(payload(), now=100)
    first = store.claim(1, now=100)[0]
    assert store.recover(max_attempts=3, now=101) == 1
    second = store.claim(1, now=102)[0]
    assert first['id'] == second['id']
    assert first['lease_token'] != second['lease_token']
    assert store.finish(first['id'], first['lease_token'], now=103) is False
    assert store.get_message(receipt['message_id'])['deliveries'][0]['status'] == 'sending'
    assert store.finish(second['id'], second['lease_token'], now=104) is True
    result = store.get_message(receipt['message_id'])['deliveries'][0]
    assert result['status'] == 'sent'
    assert result['attempts'] == 2
    assert store.finish(first['id'], first['lease_token'], error='stale_failed_attempt', now=105) is False
    assert store.get_message(receipt['message_id'])['deliveries'][0]['status'] == 'sent'


def test_retry_budget_backoff_cap_and_manual_retry_preserve_total_attempts(store, target):
    receipt = store.receive(payload(), now=100)
    first = store.claim(1, now=100)[0]
    assert store.finish(first['id'], first['lease_token'], error='provider_unavailable',
                        max_attempts=3, backoff_base_seconds=5, backoff_max_seconds=10, now=101)
    result = store.get_message(receipt['message_id'])['deliveries'][0]
    assert result['status'] == 'retry'
    assert result['last_error'] == 'provider_unavailable'
    assert result['attempts'] == 1
    assert store.claim(1, now=105) == []
    second = store.claim(1, now=106)[0]
    store.finish(second['id'], second['lease_token'], error='timeout', max_attempts=3,
                 backoff_base_seconds=5, backoff_max_seconds=10, now=107)
    assert store.claim(1, now=116) == []
    third = store.claim(1, now=117)[0]
    store.finish(third['id'], third['lease_token'], error='timeout', max_attempts=3,
                 backoff_base_seconds=5, backoff_max_seconds=10, now=118)
    failed = store.get_message(receipt['message_id'])['deliveries'][0]
    assert failed['status'] == 'failed'
    assert failed['attempts'] == 3
    assert failed['last_error'] == 'timeout'
    assert store.claim(1, now=10000) == []
    retry = store.manual_retry(first['id'], now=10001)
    assert retry['status'] == 'pending'
    assert retry['attempts'] == 3
    after_manual = store.claim(1, now=10001)[0]
    store.finish(after_manual['id'], after_manual['lease_token'], now=10002)
    completed = store.get_message(receipt['message_id'])['deliveries'][0]
    assert completed['status'] == 'sent'
    assert completed['attempts'] == 4


def test_repeated_crashes_cannot_bypass_the_finite_automatic_attempt_budget(store, target):
    receipt = store.receive(payload(), now=100)
    for attempt in range(3):
        assert len(store.claim(1, max_attempts=3, now=100 + attempt * 2)) == 1
        assert store.recover(max_attempts=3, now=101 + attempt * 2) == 1
    delivery = store.get_message(receipt['message_id'])['deliveries'][0]
    assert delivery['status'] == 'failed'
    assert delivery['attempts'] == 3
    assert store.claim(1, max_attempts=3, now=10000) == []


def test_only_failed_deliveries_can_be_manually_retried(store, target):
    from backend.store import StoreError

    receipt = store.receive(payload(), now=100)
    delivery = store.get_message(receipt['message_id'])['deliveries'][0]
    with pytest.raises(StoreError) as pending:
        store.manual_retry(delivery['id'], now=100)
    assert pending.value.status == 409
    claim = store.claim(1, now=101)[0]
    store.finish(claim['id'], claim['lease_token'], now=102)
    with pytest.raises(StoreError) as sent:
        store.manual_retry(delivery['id'], now=103)
    assert sent.value.status == 409


def test_cleanup_uses_last_success_time_and_preserves_all_unfinished_work(store, target, target_body, settings):
    old = store.receive(payload(body='old completed'), now=100)
    claim = store.claim(1, now=100)[0]
    store.finish(claim['id'], claim['lease_token'], now=200)

    late = store.receive(payload(body='old receipt but recently delivered'), now=101)
    claim = store.claim(1, now=102)[0]
    store.finish(claim['id'], claim['lease_token'], now=190000)

    failed = store.receive(payload(body='failed must remain recoverable'), now=103)
    claim = store.claim(1, now=104)[0]
    store.finish(claim['id'], claim['lease_token'], error='offline', max_attempts=1, now=105)

    other = make_target(store, target_body, name='Second destination', is_default=False)
    mixed = store.receive(payload(body='one success one unfinished', target_ids=[target['id'], other['id']]), now=106)
    claims = store.claim(2, now=107)
    assert len(claims) == 2
    store.finish(claims[0]['id'], claims[0]['lease_token'], now=108)
    pending = store.receive(payload(body='never attempted'), now=109)

    assert store.cleanup(retention_days=1, now=200000) == 1
    with sqlite3.connect(settings.database_path) as db:
        ids = {row[0] for row in db.execute('SELECT id FROM messages')}
    assert old['message_id'] not in ids
    assert ids == {r['message_id'] for r in (late, failed, mixed, pending)}
    assert len(store.get_message(mixed['message_id'])['deliveries']) == 2
    assert store.get_message(failed['message_id'])['deliveries'][0]['last_error'] == 'offline'
    assert store.cleanup(retention_days=1, now=200000) == 0


def test_completed_target_can_be_deleted_without_erasing_delivery_history(store, target):
    receipt = store.receive(payload(), now=100)
    claim = store.claim(1, now=101)[0]
    store.finish(claim['id'], claim['lease_token'], now=102)
    store.delete_target(target['id'])
    detail = store.get_message(receipt['message_id'])
    assert len(detail['deliveries']) == 1
    assert detail['deliveries'][0]['status'] == 'sent'
    assert detail['deliveries'][0]['target_name'] == target['name']


def test_duplicate_explicit_target_order_is_canonicalized(store, target, target_body):
    other = make_target(store, target_body, name='Second destination', is_default=False)
    first = store.receive(payload(idempotency_key='same-destinations', target_ids=[target['id'], other['id']]))
    repeated = store.receive(payload(idempotency_key='same-destinations', target_ids=[other['id'], target['id'], other['id']]))
    assert repeated == {'message_id': first['message_id'], 'duplicate': True}
    assert len(store.get_message(first['message_id'])['deliveries']) == 2


def test_target_protocol_cannot_change_with_unfinished_delivery(store, target, target_body):
    from backend.store import StoreError

    store.receive(payload())
    mqtt = {**target_body, 'kind': 'mqtt', 'config': {'broker_host': '8.8.8.8', 'topic': 'messages'}}
    with pytest.raises(StoreError) as failed:
        store.update_target(target['id'], mqtt)
    assert failed.value.status == 409
    assert store.list_targets()[0]['kind'] == 'ntfy'


def test_concurrent_target_update_cannot_change_protocol_under_new_pending_work(store, target, target_body, monkeypatch):
    import backend.store as store_module
    from backend.store import StoreError

    normalize = store_module.normalize_target_config
    intervened = False

    def racing_validation(kind, config):
        nonlocal intervened
        if not intervened:
            intervened = True
            store.update_target(target['id'], {
                **target_body, 'kind': 'mqtt',
                'config': {'broker_host': '8.8.8.8', 'topic': 'messages'},
            })
            store.receive(payload(target_ids=[target['id']]))
        return normalize(kind, config)

    monkeypatch.setattr(store_module, 'normalize_target_config', racing_validation)
    with pytest.raises(StoreError) as conflict:
        store.update_target(target['id'], {**target_body, 'name': 'Stale update'})
    assert conflict.value.status == 409
    assert store.list_targets()[0]['kind'] == 'mqtt'
    deliveries = store.list_messages()['messages'][0]['deliveries']
    assert len(deliveries) == 1
    assert deliveries[0]['status'] == 'pending'


def test_wrong_encryption_key_fails_closed_without_replacing_stored_credentials(store, target, settings):
    from cryptography.fernet import Fernet, InvalidToken

    with sqlite3.connect(settings.database_path) as db:
        original = db.execute('SELECT config_encrypted FROM targets WHERE id=?', (target['id'],)).fetchone()[0]
    wrong_key = Store(settings.database_path, Fernet.generate_key().decode())
    with pytest.raises(InvalidToken):
        wrong_key.initialize()
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT config_encrypted FROM targets WHERE id=?', (target['id'],)).fetchone()[0] == original
    store.initialize()
    assert store.list_targets()[0]['id'] == target['id']
