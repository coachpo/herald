# backend/tests/AGENTS.md

## Overview

Pytest suite for backend behavior against a real PostgreSQL database. No SQLite path and no coverage tool are configured.

## Database Fixtures

- `TEST_DATABASE_URL` defaults to `postgresql://herald:herald@127.0.0.1:5432/herald`.
- Session fixture runs migrations once with `apply_migrations(TEST_DATABASE_URL)`.
- Autouse fixture truncates `users, refresh_tokens, ingest_endpoints, channels, rules, messages, deliveries` before every test.
- Test env sets `DB_POOL_CLASS=null` and clears settings/database caches around each test.
- Data helpers insert rows directly with asyncpg; channel fixture encrypts config before insert.

## Patterns

- API tests use `httpx.AsyncClient` with `ASGITransport(app=app)` and `base_url="http://test"`.
- Async tests are explicitly marked with `@pytest.mark.asyncio`.
- Config-sensitive tests set env with `monkeypatch`, clear `get_settings.cache_clear()`, and recreate the app.
- Keep fixture SQL close to migration columns; reflected table state comes from the migrated schema.
- Provider tests should assert request shape and SSRF behavior without leaking secrets.

## Command Notes

```bash
TEST_DATABASE_URL=postgresql://herald:herald@127.0.0.1:35432/herald_dev uv run --project backend --locked pytest backend/tests -v
```

Use this variant with the `start.sh` development database. Root `AGENTS.md` carries the default pytest command.

## Do Not

- Do not add SQLite-only test paths.
- Do not assume test order; every test should pass after table truncation.
- Do not store plaintext provider secrets in expected logs or snapshots.
