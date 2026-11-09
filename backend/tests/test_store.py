from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import sqlite3
import threading

import pytest

from backend.store import Store, StoreError


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


def routing_rule(rule_id, *targets, enabled=True, minimum=3):
    return {'id': rule_id, 'enabled': enabled,
            'all': [{'field': 'priority', 'op': 'gte', 'value': minimum}],
            'target_ids': [target['id'] for target in targets]}


def test_rules_union_without_defaults_and_explicit_selection_bypasses_routing(store, target_body):
    default = make_target(store, target_body)
    first = make_target(store, target_body, name='Rule A', is_default=False)
    second = make_target(store, target_body, name='Rule B', is_default=False)
    store.update_routing({'revision': 0, 'rules': [
        routing_rule('first', first), routing_rule('overlap', first, second)]})
    receipt = store.receive(payload())
    message = store.get_message(receipt['message_id'])
    assert {d['target_id'] for d in message['deliveries']} == {first['id'], second['id']}
    assert message['routing_decision'] == {
        'mode': 'rules', 'rules_revision': 1, 'matched_rule_ids': ['first', 'overlap']}
    explicit = store.receive(payload(target_ids=[default['id'], default['id']]))
    detail = store.get_message(explicit['message_id'])
    assert [d['target_id'] for d in detail['deliveries']] == [default['id']]
    assert detail['routing_decision'] == {
        'mode': 'explicit', 'rules_revision': None, 'matched_rule_ids': []}
    assert store.list_messages()['messages'][0]['routing_decision'] == detail['routing_decision']
    assert 'routing_decision_json' not in message


def test_rules_zero_matches_fall_back_only_to_enabled_defaults(store, target_body):
    default = make_target(store, target_body)
    make_target(store, target_body, name='Disabled default', enabled=False)
    routed = make_target(store, target_body, name='Rule only', is_default=False)
    store.update_routing({'revision': 0, 'rules': [routing_rule('urgent', routed, minimum=5)]})
    receipt = store.receive(payload(priority=1))
    message = store.get_message(receipt['message_id'])
    assert [d['target_id'] for d in message['deliveries']] == [default['id']]
    assert message['routing_decision'] == {
        'mode': 'defaults', 'rules_revision': 1, 'matched_rule_ids': []}


def test_rule_replay_keeps_original_fingerprint_targets_and_decision(store, target_body, settings):
    original = make_target(store, target_body, is_default=False)
    replacement = make_target(store, target_body, name='Replacement', is_default=False)
    store.update_routing({'revision': 0, 'rules': [routing_rule('original', original)]})
    request = payload(idempotency_key='original-rules')
    receipt = store.receive(request)
    canonical = {'title': request['title'], 'body': request['body'],
                 'priority': request['priority'], 'target_ids': None}
    expected_hash = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(',', ':'),
                                             ensure_ascii=False).encode()).hexdigest()
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT content_hash FROM messages').fetchone()[0] == expected_hash
    store.update_routing({'revision': 1, 'rules': [routing_rule('replacement', replacement)]})
    store.update_target(original['id'], {**target_body, 'is_default': False, 'enabled': False})
    assert store.receive(request) == {'message_id': receipt['message_id'], 'duplicate': True}
    with pytest.raises(StoreError, match='idempotency_conflict'):
        store.receive({**request, 'body': 'changed'})
    message = store.get_message(receipt['message_id'])
    assert [d['target_id'] for d in message['deliveries']] == [original['id']]
    assert message['routing_decision']['matched_rule_ids'] == ['original']
    assert message['routing_decision']['rules_revision'] == 1
    assert len(store.list_messages()['messages']) == 1


def test_selected_disabled_target_rejects_entire_rule_fanout_without_fallback(store, target_body, settings):
    make_target(store, target_body)
    active = make_target(store, target_body, name='Selected active', is_default=False)
    disabled = make_target(store, target_body, name='Selected disabled', is_default=False, enabled=False)
    # Existing disabled targets may be referenced by configuration, but selecting
    # one must reject the whole receive rather than silently using defaults.
    store.update_routing({'revision': 0, 'rules': [routing_rule('both', active, disabled)]})
    for requested in (None, [active['id'], disabled['id']], [active['id'], 'missing']):
        with pytest.raises(StoreError, match='target_unavailable'):
            store.receive(payload(target_ids=requested))
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 0


def test_rule_receipt_and_decision_commit_together_or_rollback(store, target_body, settings):
    targets = [make_target(store, target_body, name=f'Rule target {i}', is_default=False) for i in range(2)]
    store.update_routing({'revision': 0, 'rules': [routing_rule('both', *targets)]})
    with sqlite3.connect(settings.database_path) as db:
        db.execute("""CREATE TRIGGER fail_second_rule_delivery BEFORE INSERT ON deliveries
            WHEN (SELECT COUNT(*) FROM deliveries)=1
            BEGIN SELECT RAISE(ABORT, 'simulated fanout failure'); END""")
    with pytest.raises(sqlite3.IntegrityError):
        store.receive(payload(idempotency_key='atomic-routing'))
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 0
        db.execute('DROP TRIGGER fail_second_rule_delivery')
    receipt = store.receive(payload(idempotency_key='atomic-routing'))
    with sqlite3.connect(settings.database_path) as db:
        row = db.execute('SELECT routing_decision_json FROM messages WHERE id=?',
                         (receipt['message_id'],)).fetchone()
        assert json.loads(row[0]) == {'mode': 'rules', 'rules_revision': 1, 'matched_rule_ids': ['both']}
        assert db.execute('SELECT COUNT(*) FROM deliveries WHERE message_id=?',
                          (receipt['message_id'],)).fetchone()[0] == 2


def test_concurrent_config_updates_compare_revision_inside_write_transaction(store, target):
    barrier = threading.Barrier(2)

    def update(rule_id):
        barrier.wait(timeout=2)
        try:
            return store.update_routing({'revision': 0, 'rules': [routing_rule(rule_id, target)]})
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ('a', 'b')))
    assert results.count('routing_changed') == 1
    successes = [result for result in results if isinstance(result, dict)]
    assert len(successes) == 1
    assert store.get_routing() == successes[0]
    assert successes[0]['revision'] == 1


@pytest.mark.parametrize('first_operation', ['receive', 'update'])
def test_config_update_and_receipt_use_one_serialized_config_version(store, target_body, monkeypatch, first_operation):
    old = make_target(store, target_body, name='Old', is_default=False)
    new = make_target(store, target_body, name='New', is_default=False)
    store.update_routing({'revision': 0, 'rules': [routing_rule('old', old)]})
    transaction_owned = threading.Event()
    other_started = threading.Event()
    release = threading.Event()
    local = threading.local()
    read = store._routing

    def pause_with_write_lock(db):
        value = read(db)
        if getattr(local, 'operation', None) == first_operation:
            transaction_owned.set()
            assert release.wait(2), 'test did not release first write transaction'
        return value

    monkeypatch.setattr(store, '_routing', pause_with_write_lock)

    def operation(name):
        local.operation = name
        if name != first_operation:
            other_started.set()
        if name == 'receive':
            return store.receive(payload())
        return store.update_routing({'revision': 1, 'rules': [routing_rule('new', new)]})

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(operation, first_operation)
        try:
            assert transaction_owned.wait(2)
            second = pool.submit(operation, 'update' if first_operation == 'receive' else 'receive')
            assert other_started.wait(2)
        finally:
            release.set()
        results = [first.result(), second.result()]
    receipt = next(result for result in results if 'message_id' in result)
    message = store.get_message(receipt['message_id'])
    expected_rule, expected_target, expected_revision = (
        ('old', old, 1) if first_operation == 'receive' else ('new', new, 2))
    assert message['routing_decision'] == {
        'mode': 'rules', 'rules_revision': expected_revision, 'matched_rule_ids': [expected_rule]}
    assert [d['target_id'] for d in message['deliveries']] == [expected_target['id']]
    assert store.get_routing()['revision'] == 2


@pytest.mark.parametrize('enabled', [True, False])
def test_delete_and_rule_update_cannot_leave_dangling_references(store, target, enabled):
    barrier = threading.Barrier(2)

    def operation(name):
        barrier.wait(timeout=2)
        try:
            if name == 'delete':
                store.delete_target(target['id'])
            else:
                store.update_routing({'revision': 0, 'rules': [routing_rule('reference', target, enabled=enabled)]})
            return name + '_ok'
        except StoreError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = set(pool.map(operation, ('delete', 'update')))
    assert results in ({'delete_ok', 'target_unavailable'},
                       {'update_ok', 'target_referenced_by_routing'})
    existing = {target['id'] for target in store.list_targets()}
    assert all(set(rule['target_ids']) <= existing for rule in store.get_routing()['rules'])
