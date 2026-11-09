# backend/AGENTS.md

## Boundaries

- `api.py` handles HTTP parsing/authentication and calls `store.Store` for durable operations.
- `store.py` owns SQLite schema and transactions. Use stdlib sqlite3, WAL, synchronous FULL, foreign keys, and bounded busy timeout. No network operation may hold a database transaction.
- `app.py` owns the exclusive data-directory lock and one lifespan delivery worker. `cli.py` starts one HTTP process; do not introduce multi-worker startup.
- `worker.py` claims bounded work, counts attempts before sends, persists outcomes, and recovers interrupted sends. Only failed deliveries may be manually retried; never resend sent deliveries.
- `channel_dispatch.py` and `providers/` own provider serialization and transport. Retain shared SSRF protections and sanitize transport errors.
- `config.py` creates or loads private local credentials. `security.py` keeps admin and ingest tokens separate. Never print token/key values.
- Encrypt target configurations using `core/crypto.py`; expose only redacted configuration in APIs. Send both external-ingest and dashboard messages through the same receipt transaction.

## Validation

From the repository root, Python 3.13+ and uv:

```bash
uv sync --project backend --locked
uv run --project backend --locked pytest backend/tests -q
uv run --project backend --locked herald-backend
```

Tests use disposable SQLite files and mocked provider transports. No external database is needed. See [Operations](../docs/07_operations.md); do not start services for documentation-only checks.
