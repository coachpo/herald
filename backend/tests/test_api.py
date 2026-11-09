from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


def receive(client, headers, **changes):
    payload = {'body': 'Persist before acknowledging', 'title': 'Receipt', 'priority': 3}
    payload.update(changes)
    return client.post('/api/ingest', headers=headers, json=payload)


def test_management_and_ingest_credentials_have_separate_scope(client, admin_headers, ingest_headers):
    assert client.get('/api/session').status_code == 401
    assert client.get('/api/session', headers=ingest_headers).status_code == 401
    assert client.get('/api/session', headers=admin_headers).json() == {'authenticated': True}
    assert client.get('/api/targets', headers=ingest_headers).status_code == 401
    assert receive(client, admin_headers).status_code == 401
    assert client.post('/api/messages', headers=ingest_headers, json={'body': 'x'}).status_code == 401
    assert receive(client, {'Authorization': 'Bearer incorrect'}).status_code == 401


def test_receipt_commits_message_and_delivery_before_success(client, api_target, ingest_headers, admin_headers, settings):
    response = receive(client, ingest_headers)
    assert response.status_code == 201, response.text
    assert response.json()['duplicate'] is False
    message_id = response.json()['message_id']
    # Read using another connection after ACK: the transaction must already be durable.
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT body FROM messages WHERE id=?', (message_id,)).fetchone()[0] == 'Persist before acknowledging'
        assert db.execute('SELECT COUNT(*) FROM deliveries WHERE message_id=?', (message_id,)).fetchone()[0] == 1
    detail = client.get('/api/messages/' + message_id, headers=admin_headers).json()
    assert detail['body'] == 'Persist before acknowledging'
    assert len(detail['deliveries']) == 1
    assert detail['deliveries'][0]['status'] == 'pending'
    assert detail['deliveries'][0]['attempts'] == 0


def test_storage_failure_never_acknowledges_and_rolls_back_message(client, api_target, ingest_headers, settings):
    with sqlite3.connect(settings.database_path) as db:
        db.execute("CREATE TRIGGER fail_delivery BEFORE INSERT ON deliveries BEGIN SELECT RAISE(ABORT, 'simulated disk transaction failure'); END")
    response = receive(client, ingest_headers)
    assert response.status_code == 503, response.text
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM deliveries').fetchone()[0] == 0


def test_management_send_uses_same_receipt_and_idempotency_flow(client, api_target, ingest_headers, admin_headers):
    payload = {'body': 'shared receive transaction', 'idempotency_key': 'one-receipt'}
    sent = client.post('/api/messages', headers=admin_headers, json=payload)
    assert sent.status_code == 201
    repeated = client.post('/api/ingest', headers=ingest_headers, json=payload)
    assert repeated.status_code == 200
    assert repeated.json() == {'message_id': sent.json()['message_id'], 'duplicate': True}
    changed = client.post('/api/ingest', headers=ingest_headers, json={**payload, 'body': 'different content'})
    assert changed.status_code == 409
    listing = client.get('/api/messages', headers=admin_headers).json()['messages']
    assert len(listing) == 1


def test_without_idempotency_key_repeated_content_is_a_new_receipt(client, api_target, ingest_headers):
    first, second = receive(client, ingest_headers), receive(client, ingest_headers)
    assert first.status_code == second.status_code == 201
    assert first.json()['message_id'] != second.json()['message_id']


def test_explicit_multiple_targets_are_persisted_independently(client, api_target, target_body, admin_headers, ingest_headers):
    second = client.post('/api/targets', headers=admin_headers, json={**target_body, 'name': 'Secondary', 'is_default': False}).json()
    response = receive(client, ingest_headers, target_ids=[api_target['id'], second['id']])
    assert response.status_code == 201
    detail = client.get('/api/messages/' + response.json()['message_id'], headers=admin_headers).json()
    assert {d['target_id'] for d in detail['deliveries']} == {api_target['id'], second['id']}
    assert all(d['attempts'] == 0 and d['status'] == 'pending' for d in detail['deliveries'])


def test_no_destination_or_unknown_destination_is_not_silent_success(client, ingest_headers, admin_headers, settings):
    assert receive(client, ingest_headers).status_code == 400
    assert receive(client, ingest_headers, target_ids=['missing-target']).status_code == 400
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0


def test_pending_delivery_prevents_target_deletion(client, api_target, ingest_headers, admin_headers):
    response = receive(client, ingest_headers)
    assert response.status_code == 201
    deletion = client.delete('/api/targets/' + api_target['id'], headers=admin_headers)
    assert deletion.status_code == 409
    detail = client.get('/api/messages/' + response.json()['message_id'], headers=admin_headers).json()
    assert len(detail['deliveries']) == 1
    assert detail['deliveries'][0]['target_id'] == api_target['id']


def test_target_secrets_are_encrypted_and_not_returned(client, api_target, settings, admin_headers, target_body, store):
    secret = target_body['config']['access_token']
    assert secret not in str(api_target)
    response = client.get('/api/targets', headers=admin_headers)
    assert response.status_code == 200
    assert secret not in response.text
    with sqlite3.connect(settings.database_path) as db:
        assert secret not in str(db.execute('SELECT * FROM targets').fetchall())
    # Blank/omitted secret during edit preserves the existing stored credential.
    replacement = {**target_body, 'name': 'Renamed', 'config': {'server_base_url': 'https://8.8.8.8', 'topic': 'new-topic'}}
    changed = client.put('/api/targets/' + api_target['id'], headers=admin_headers, json=replacement)
    assert changed.status_code == 200, changed.text
    assert secret not in changed.text
    store.receive({'body': 'verify edited destination credentials'})
    claimed = store.claim(1)
    assert claimed[0]['config']['access_token'] == secret
    assert claimed[0]['config']['topic'] == 'new-topic'


def test_validation_errors_never_echo_supplied_credentials(client, admin_headers, target_body):
    secret = 'never-echo-this-secret-value'
    response = client.post('/api/targets', headers=admin_headers, json={**target_body, 'config': {**target_body['config'], 'unexpected': secret}})
    assert response.status_code == 422
    assert secret not in response.text
    assert target_body['config']['access_token'] not in response.text


@pytest.mark.parametrize('payload', [
    {'body': ''},
    {'body': 'x', 'priority': True},
    {'body': 'x', 'priority': 6},
    {'body': 'x', 'unknown': 'field'},
])
def test_invalid_message_is_rejected_without_partial_storage(client, api_target, ingest_headers, payload, settings):
    response = client.post('/api/ingest', headers=ingest_headers, json=payload)
    assert response.status_code == 422, response.text
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0


def test_retry_does_not_offer_successful_message_replay_or_pending_retry(client, api_target, ingest_headers, admin_headers):
    response = receive(client, ingest_headers)
    message_id = response.json()['message_id']
    delivery_id = client.get('/api/messages/' + message_id, headers=admin_headers).json()['deliveries'][0]['id']
    assert client.post('/api/deliveries/' + delivery_id + '/retry', headers=admin_headers).status_code == 409
    assert client.post('/api/messages/' + message_id + '/replay', headers=admin_headers).status_code in {404, 405}


def test_second_process_cannot_open_same_database_while_running(client, settings):
    with pytest.raises(RuntimeError, match='already|lock|running'):
        with TestClient(create_app(settings=settings, start_worker=False)):
            pass


def test_generated_credentials_are_private_stable_and_not_default(tmp_path, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv('HERALD_DATA_DIR', str(tmp_path / 'new-data'))
    for name in ('HERALD_ADMIN_TOKEN', 'HERALD_INGEST_TOKEN', 'HERALD_ENCRYPTION_KEY'):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    try:
        first = get_settings()
        path = first.data_dir / 'credentials.env'
        assert path.stat().st_mode & 0o777 == 0o600
        assert first.data_dir.stat().st_mode & 0o777 == 0o700
        assert len(first.admin_token) >= 32 and len(first.ingest_token) >= 32
        assert first.admin_token != first.ingest_token
        get_settings.cache_clear()
        second = get_settings()
        assert first.admin_token == second.admin_token
        assert first.ingest_token == second.ingest_token
        assert first.encryption_key == second.encryption_key
    finally:
        get_settings.cache_clear()


def test_partial_credential_configuration_is_rejected(tmp_path, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv('HERALD_DATA_DIR', str(tmp_path / 'new-data'))
    monkeypatch.setenv('HERALD_ADMIN_TOKEN', 'a' * 40)
    monkeypatch.delenv('HERALD_INGEST_TOKEN', raising=False)
    monkeypatch.delenv('HERALD_ENCRYPTION_KEY', raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match='all three'):
            get_settings()
        assert not (tmp_path / 'new-data' / 'credentials.env').exists()
    finally:
        get_settings.cache_clear()


def test_http_ingest_only_acknowledges_valid_json_protocol(client, api_target, ingest_headers, settings):
    malformed = client.post('/api/ingest', headers={**ingest_headers, 'Content-Type': 'application/json'}, content=b'not-json')
    assert malformed.status_code == 422
    unsupported = client.post('/api/ingest', headers={**ingest_headers, 'Content-Type': 'text/plain'}, content=b'{"body":"x"}')
    assert unsupported.status_code == 415
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0


def test_real_background_delivery_does_not_delay_receipt_acknowledgement(settings, store, target, ingest_headers, monkeypatch):
    import asyncio
    from dataclasses import replace
    import threading
    import time
    import backend.worker as worker_module

    dispatch_started = threading.Event()
    release_provider = threading.Event()

    async def unavailable_provider(kind, config, message, *, timeout):
        dispatch_started.set()
        while not release_provider.is_set():
            await asyncio.sleep(0.002)
        return {'http_status': 200}

    monkeypatch.setattr(worker_module, 'dispatch', unavailable_provider)
    app = create_app(settings=replace(settings, delivery_timeout=10), store=store)
    try:
        with TestClient(app) as client:
            before = time.monotonic()
            response = receive(client, ingest_headers)
            elapsed = time.monotonic() - before
            assert response.status_code == 201
            assert elapsed < 1, 'ACK waited for downstream instead of the durable receipt transaction'
            assert dispatch_started.wait(1)
            assert not release_provider.is_set()
            detail = store.get_message(response.json()['message_id'])
            assert detail['deliveries'][0]['status'] == 'sending'
            release_provider.set()
            deadline = time.monotonic() + 1
            while store.get_message(response.json()['message_id'])['deliveries'][0]['status'] != 'sent':
                assert time.monotonic() < deadline
                time.sleep(0.002)
    finally:
        release_provider.set()


def test_oversized_message_never_creates_receipt(client, api_target, ingest_headers, settings):
    response = client.post('/api/ingest', headers=ingest_headers,
                           json={'body': 'x' * (1024 * 1024)})
    assert response.status_code == 413
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute('SELECT COUNT(*) FROM messages').fetchone()[0] == 0
