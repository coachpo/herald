# Herald Backend

Async FastAPI backend for Herald with PostgreSQL, numbered SQL migrations, structured logging, and an async delivery worker.

## Quick Start

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
```

Run the worker separately:

```bash
uv run --project backend --locked python -m backend.worker
```

## Tests

```bash
docker start herald-test-pg 2>/dev/null || docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald -p 5432:5432 postgres:16-alpine
uv run --project backend --locked pytest backend/tests -v
```

Tests read `TEST_DATABASE_URL` and default to `postgresql://herald:herald@127.0.0.1:5432/herald`.

## Health

`GET /health` returns database connectivity status and version info.

## Configuration

See `docs/07_operations.md`.
