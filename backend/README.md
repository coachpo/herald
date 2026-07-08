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
uv run --project backend --locked pytest backend/tests -v
```

## Health

`GET /health` returns database connectivity status and version info.

## Configuration

See `docs/07_operations.md`.
