from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone

import asyncpg
import pytest

from backend.config import get_settings
from backend.database import clear_database_state
from backend.migrate import apply_migrations

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://herald:herald@127.0.0.1:5432/herald",
)
TEST_JWT_SIGNING_KEY = "test-jwt-signing-key-0123456789abcdef"
TEST_SECRET_KEY = "test-secret-key-0123456789abcdef"
TEST_ENCRYPTION_KEY = "dKkPUi_l6pJiD24yQWhv14jArlTc95xJMu38xpv8uKc="

_ALL_TABLES = "users, refresh_tokens, ingest_endpoints, channels, rules, messages, deliveries"


@pytest.fixture(autouse=True)
def configure_backend_test_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", TEST_SECRET_KEY)
    monkeypatch.setenv("JWT_SIGNING_KEY", TEST_JWT_SIGNING_KEY)
    monkeypatch.setenv("CHANNEL_CONFIG_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    monkeypatch.setenv("DB_POOL_CLASS", "null")
    get_settings.cache_clear()
    clear_database_state()
    yield
    get_settings.cache_clear()
    clear_database_state()


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    asyncio.run(apply_migrations(TEST_DATABASE_URL))
    yield


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_database):
    asyncio.run(_truncate_all())
    yield


async def _truncate_all() -> None:
    conn = await asyncpg.connect(TEST_DATABASE_URL)
    try:
        await conn.execute(f"TRUNCATE {_ALL_TABLES} CASCADE")
    finally:
        await conn.close()


def _run_sql(query: str, *args):
    """Loop-safe sync SQL helper for sync fixtures and async test bodies."""

    async def _go():
        conn = await asyncpg.connect(TEST_DATABASE_URL)
        try:
            return await conn.fetchrow(query, *args)
        finally:
            await conn.close()

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_go())
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _go()).result()


@pytest.fixture
def app(configure_backend_test_env):
    from backend.app import create_app

    return create_app()


@pytest.fixture
def make_user(configure_backend_test_env):
    from backend.auth.passwords import make_password

    def _make(email: str = "u@example.com", password: str = "pw-123456") -> dict:
        user_id = uuid.uuid4()
        _run_sql(
            "INSERT INTO users (id, email, password, is_active, created_at) "
            "VALUES ($1, $2, $3, TRUE, $4)",
            user_id,
            email,
            make_password(password),
            datetime.now(timezone.utc),
        )
        return {"id": user_id, "email": email, "password": password}

    return _make


@pytest.fixture
def make_ingest_endpoint(configure_backend_test_env):
    from backend.auth.tokens import generate_secret_token, hash_token, sha256_hex

    def _make(user_id, name: str = "ep") -> dict:
        endpoint_id = uuid.uuid4()
        raw_key = generate_secret_token(32)
        _run_sql(
            "INSERT INTO ingest_endpoints (id, user_id, name, token_hash, key_sha256, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            endpoint_id,
            user_id,
            name,
            hash_token(raw_key),
            sha256_hex(raw_key),
            datetime.now(timezone.utc),
        )
        return {"id": endpoint_id, "raw_key": raw_key, "name": name}

    return _make


@pytest.fixture
def make_channel(configure_backend_test_env):
    import json as _json

    from backend.core.crypto import encrypt_json_bytes

    def _make(
        user_id, type_: str = "ntfy", config: dict | None = None, name: str = "ch"
    ) -> dict:
        channel_id = uuid.uuid4()
        cfg = config or {"server_base_url": "https://ntfy.example.com", "topic": "t"}
        _run_sql(
            "INSERT INTO channels (id, user_id, type, name, config_json_encrypted, created_at) "
            "VALUES ($1, $2, $3, $4, $5, $6)",
            channel_id,
            user_id,
            type_,
            name,
            encrypt_json_bytes(_json.dumps(cfg).encode("utf-8")),
            datetime.now(timezone.utc),
        )
        return {"id": channel_id, "type": type_, "config": cfg}

    return _make


@pytest.fixture
def make_rule(configure_backend_test_env):
    import json as _json

    def _make(
        user_id,
        channel_id,
        filter_json: dict | None = None,
        payload_template: dict | None = None,
        enabled: bool = True,
    ) -> dict:
        rule_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        _run_sql(
            "INSERT INTO rules (id, user_id, name, enabled, filter_json, channel_id, "
            "payload_template_json, created_at, updated_at) "
            "VALUES ($1, $2, 'r', $3, $4, $5, $6, $7, $7)",
            rule_id,
            user_id,
            enabled,
            _json.dumps(filter_json or {}),
            channel_id,
            _json.dumps(payload_template or {}),
            now,
        )
        return {"id": rule_id, "channel_id": channel_id}

    return _make
