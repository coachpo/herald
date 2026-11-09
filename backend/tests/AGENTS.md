# backend/tests/AGENTS.md

## Destructive Fixture Boundary

- Use only a dedicated disposable PostgreSQL database; there is no SQLite test path. `TEST_DATABASE_URL` defaults to `postgresql://herald:herald@127.0.0.1:5432/herald`.
- The autouse session fixture applies migrations; before every test, fixtures truncate `users, refresh_tokens, ingest_endpoints, channels, rules, messages, deliveries` with `CASCADE`.
- Fixtures set `DB_POOL_CLASS=null` and clear settings/database caches around tests. Data helpers insert rows with asyncpg and encrypt channel configs.
- Do not point tests at a development database containing data you need to keep. The `start.sh` database is not isolated from its running API/worker.

## Test Patterns

- API tests use `httpx.AsyncClient` with `ASGITransport(app=app)` and `base_url="http://test"`.
- Mark async tests with `@pytest.mark.asyncio`.
- For config-sensitive tests, set env with `monkeypatch`, clear `get_settings.cache_clear()`, and recreate the app.
- Keep fixture SQL aligned with migrations and tests independent of execution order.
- Provider tests should mock external transports and assert request shape and SSRF behavior without exposing plaintext secrets in logs/snapshots.
- Use the parent guide's pytest command, narrowing to affected test files where appropriate.
