from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app import create_app
from backend.config import Settings
from backend.store import Store


@pytest.fixture
def settings(tmp_path):
    return Settings(
        data_dir=tmp_path / 'herald-data',
        admin_token='test-admin-token-' + 'a' * 32,
        ingest_token='test-ingest-token-' + 'b' * 32,
        encryption_key=Fernet.generate_key().decode(),
        delivery_timeout=0.1,
        max_attempts=3,
        backoff_base_seconds=5,
        backoff_max_seconds=10,
        retention_days=30,
        concurrency=2,
        poll_seconds=0.01,
    )


@pytest.fixture
def store(settings):
    instance = Store(settings.database_path, settings.encryption_key)
    instance.initialize()
    return instance


@pytest.fixture
def client(settings, store):
    with TestClient(create_app(settings=settings, store=store, start_worker=False)) as value:
        yield value


@pytest.fixture
def admin_headers(settings):
    return {'Authorization': 'Bearer ' + settings.admin_token}


@pytest.fixture
def ingest_headers(settings):
    return {'Authorization': 'Bearer ' + settings.ingest_token}


@pytest.fixture
def target_body():
    # A literal public address avoids DNS and is never contacted by these tests.
    return {
        'name': 'Primary',
        'kind': 'ntfy',
        'is_default': True,
        'enabled': True,
        'config': {
            'server_base_url': 'https://8.8.8.8',
            'topic': 'herald-test',
            'access_token': 'test-provider-credential-not-real',
        },
    }


@pytest.fixture
def api_target(client, admin_headers, target_body):
    response = client.post('/api/targets', headers=admin_headers, json=target_body)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def target(store, target_body):
    return store.create_target(target_body)
