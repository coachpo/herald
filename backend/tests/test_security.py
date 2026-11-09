"""Credential lifecycle and errors must not reveal secrets or destroy recoverability."""
import stat
import traceback

import pytest
from cryptography.fernet import Fernet, InvalidToken
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.middleware import SafeErrorMiddleware


@pytest.fixture
def private_config_env(monkeypatch, tmp_path):
    for name in ('HERALD_ADMIN_TOKEN', 'HERALD_INGEST_TOKEN', 'HERALD_ENCRYPTION_KEY'):
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / 'private-data'
    monkeypatch.setenv('HERALD_DATA_DIR', str(root))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def test_generated_credentials_private_stable_and_not_in_repr(private_config_env):
    first = get_settings()
    path = private_config_env / 'credentials.env'
    assert stat.S_IMODE(private_config_env.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert first.admin_token != first.ingest_token
    for value in (first.admin_token, first.ingest_token, first.encryption_key):
        assert value not in repr(first)
    get_settings.cache_clear()
    second = get_settings()
    assert second.admin_token == first.admin_token
    assert second.ingest_token == first.ingest_token
    assert second.encryption_key == first.encryption_key


def test_existing_database_never_generates_replacement_key(private_config_env):
    private_config_env.mkdir(mode=0o700)
    database = private_config_env / 'herald.sqlite3'
    database.write_bytes(b'existing durable data, not a disposable new file')
    before = database.read_bytes()
    with pytest.raises(ValueError, match='existing database requires'):
        get_settings()
    assert not (private_config_env / 'credentials.env').exists()
    assert database.read_bytes() == before


def test_partial_environment_credentials_fail_without_generating_file(private_config_env, monkeypatch):
    monkeypatch.setenv('HERALD_ADMIN_TOKEN', 'sensitive-value-' + 'a' * 32)
    with pytest.raises(ValueError, match='all three') as error:
        get_settings()
    assert 'sensitive-value' not in str(error.value)
    assert not (private_config_env / 'credentials.env').exists()


def test_world_readable_data_directory_rejected(private_config_env):
    private_config_env.mkdir(mode=0o755)
    private_config_env.chmod(0o755)
    with pytest.raises(ValueError, match='private'):
        get_settings()
    assert not (private_config_env / 'credentials.env').exists()


def test_credentials_symlink_rejected(private_config_env, tmp_path):
    private_config_env.mkdir(mode=0o700)
    outside = tmp_path / 'outside-secret'
    outside.write_text('HERALD_ADMIN_TOKEN=should-never-be-used\n')
    outside.chmod(0o600)
    (private_config_env / 'credentials.env').symlink_to(outside)
    with pytest.raises(ValueError, match='private regular file'):
        get_settings()


@pytest.mark.parametrize('field,value', [('delivery_timeout', float('nan')), ('backoff_base_seconds', float('inf')), ('concurrency', 0)])
def test_invalid_worker_configuration_rejected(tmp_path, field, value):
    values = dict(data_dir=tmp_path, admin_token='a' * 32, ingest_token='b' * 32,
                  encryption_key=Fernet.generate_key().decode())
    values[field] = value
    with pytest.raises(ValueError, match='positive'):
        Settings(**values)


def test_unexpected_error_never_escapes_to_server_logger(caplog):
    app = FastAPI()
    app.add_middleware(SafeErrorMiddleware)

    @app.get('/broken')
    async def broken():
        raise RuntimeError('CREDENTIAL_FROM_PROVIDER_EXCEPTION')

    # True is intentional: an exception escaping to Uvicorn would fail this test.
    with TestClient(app, raise_server_exceptions=True) as client:
        response = client.get('/broken')
    assert response.status_code == 500
    assert response.json() == {'detail': 'internal_error'}
    assert 'CREDENTIAL_FROM_PROVIDER_EXCEPTION' not in caplog.text
    assert 'RuntimeError' in caplog.text


@pytest.mark.asyncio
async def test_started_response_error_replaces_raw_exception(caplog):
    async def broken(scope, receive, send):
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        raise ValueError('CREDENTIAL_AFTER_RESPONSE_STARTED')

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(_message):
        pass

    with pytest.raises(RuntimeError, match='^internal_error$') as error:
        await SafeErrorMiddleware(broken)({'type':'http'}, receive, send)
    formatted = ''.join(traceback.format_exception(error.value))
    assert 'CREDENTIAL_AFTER_RESPONSE_STARTED' not in formatted
    assert 'CREDENTIAL_AFTER_RESPONSE_STARTED' not in caplog.text


def test_wrong_encryption_key_fails_startup_and_preserves_targets(tmp_path, caplog):
    from backend.store import Store

    path = tmp_path / 'key-recovery' / 'herald.sqlite3'
    original_key = Fernet.generate_key().decode()
    store = Store(path, original_key)
    store.initialize()
    target = store.create_target({
        'name': 'Recoverable target', 'kind': 'bark', 'is_default': True,
        'config': {'server_base_url': 'https://8.8.8.8', 'device_key': 'PRIVATE_DEVICE_CREDENTIAL'},
    })
    with pytest.raises(InvalidToken):
        Store(path, Fernet.generate_key().decode()).initialize()
    store.initialize()
    assert [value['id'] for value in store.list_targets()] == [target['id']]
    store.receive({'body': 'still recoverable with original key'})
    delivery = store.claim()[0]
    assert delivery['config']['device_key'] == 'PRIVATE_DEVICE_CREDENTIAL'
    assert 'PRIVATE_DEVICE_CREDENTIAL' not in caplog.text
    assert original_key not in caplog.text
