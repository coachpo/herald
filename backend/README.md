# Herald Backend

Async FastAPI backend for Herald with PostgreSQL, numbered SQL migrations, structured logging, and an async delivery worker.

## Quick Start

Run these commands from the repository root with Python 3.13+, `uv`, and a reachable PostgreSQL database. For the Docker-based development setup, see [Operations](../docs/07_operations.md#local-development).

```bash
uv sync --project backend --locked
# Set this to your development database, not a production database.
export DATABASE_URL=postgresql://herald:herald@127.0.0.1:5432/herald
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
```

The API loads optional `backend/.env` settings without overriding exported variables. The migration CLI reads `DATABASE_URL` directly from the shell and does not load that file. The root `.env` is for Docker Compose, not automatically loaded by these host commands. See [environment settings](../docs/07_operations.md#environment) for secrets and production requirements.

Run the worker separately:

```bash
uv run --project backend --locked python -m backend.worker
```

## Tests

Tests require a **dedicated, disposable PostgreSQL database**: session setup applies migrations, and every test truncates all business tables. Never point `TEST_DATABASE_URL` at a development database whose contents you need, or at production.

For a new dedicated test container (requires Docker and a free host port `5432`):

```bash
docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald -e POSTGRES_PASSWORD=herald -p 5432:5432 postgres:16-alpine
docker exec herald-test-pg pg_isready -U herald -d herald
TEST_DATABASE_URL=postgresql://herald:herald@127.0.0.1:5432/herald uv run --project backend --locked pytest backend/tests -v
```

Wait until `pg_isready` reports that connections are accepted before running pytest. If that dedicated container already exists, use `docker start herald-test-pg` instead of `docker run`; if port `5432` is occupied, publish another port and adjust `TEST_DATABASE_URL` to match. Without an override, tests default to `postgresql://herald:herald@127.0.0.1:5432/herald`.

## Health

`GET /health` returns database connectivity status and version info, with HTTP `503` when the database check fails. It does not check worker or provider health.

## Configuration

See [Operations](../docs/07_operations.md), [API Guide](../docs/04_api_spec.md), and [Security And Privacy](../docs/06_security_privacy.md).
