# Herald FastAPI Backend

Async FastAPI backend for Herald with PostgreSQL, structured logging, and production-ready infrastructure.

## Quick Start

```bash
# With Docker Compose (recommended, from repo root)
docker compose up

# Manual (from repo root, Python 3.13+)
uv sync --project backend --locked
uv run --project backend --locked python backend/bootstrap_dev_db.py
uv run --project backend --locked herald-backend
```

`backend/uv.lock` is committed. Refresh it with `uv lock --project backend` when you intentionally change backend dependency metadata.

## Worker

```bash
uv run --project backend --locked python -m backend.worker
```

## Tests

```bash
uv run --project backend --locked pytest backend/tests/ -v
```

## Health

`GET /health` returns database connectivity status and version info.

## Configuration

See `docs/07_operations.md` for the full environment variable reference.
