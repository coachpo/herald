# backend/AGENTS.md

## Change Boundaries

- Keep HTTP parsing/status translation in `routes/`, business logic and transaction ownership in `services/`, provider dispatch in `channel_dispatch.py` and `providers/`.
- Use reflected tables from `database.get_tables()`, not ORM model classes. Apply numbered SQL migrations with `python -m backend.migrate` before schema-dependent work.
- Custom middleware must be pure ASGI; do not use `BaseHTTPMiddleware`.
- Channel configs stay encrypted except at validation/serialization/dispatch boundaries; use `services/channel_records.py` and `core/crypto.py`.
- API responses use dashed UUIDs via `serialize_uuid()`/schemas; public ingest also accepts dashless endpoint IDs.
- Changes to `config.py`, `database.py`, or schema exports affect routes, services, and worker. Check all affected callers.
- When changing rule semantics, check live ingest and preview/test callers together; see the [documented filter limitations](../docs/04_api_spec.md#rules).

## Commands and Prerequisites

Requires Python 3.13+, uv, and PostgreSQL. From the repository root:

```bash
uv sync --project backend --locked
# Export a reachable raw PostgreSQL DATABASE_URL before migration or startup.
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
# Separate process for queued delivery:
uv run --project backend --locked python -m backend.worker
# Dedicated disposable PostgreSQL database only; fixtures migrate and truncate it:
TEST_DATABASE_URL=postgresql://herald:herald@127.0.0.1:5432/herald uv run --project backend --locked pytest backend/tests -v
```

The migration entry point reads exported `DATABASE_URL` directly; it does not load `backend/.env`. API/worker settings load that file without overriding existing environment variables. Use a raw `postgresql://` URL; settings derive the SQLAlchemy asyncpg URL.

Password recovery uses `uv run --project backend --locked herald-backend reset-password <email>`; it mutates the selected database and prints a generated password. See [Operations](../docs/07_operations.md) for environment and recovery procedures.
