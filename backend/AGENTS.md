# backend/AGENTS.md

## Overview

FastAPI async backend for auth, ingest, persistent message storage, delivery worker, provider dispatch, and relay config export.

## Structure

```text
backend/
├── auth/          # JWT, refresh/session, password/token helpers
├── core/          # crypto, rules, templates, redaction, SSRF
├── migrations/    # numbered SQL migrations
├── providers/     # Bark, ntfy, MQTT, Gotify delivery code
├── routes/        # HTTP routes
├── schemas/       # Pydantic request/response models
├── services/      # business logic
├── tests/         # pytest suite
├── app.py
├── cli.py
├── database.py
├── edge_config.py
├── migrate.py
└── worker.py
```

## Runtime Flow

- `POST /api/ingest/{endpoint_id}` authenticates the raw key, validates JSON, handles relay headers, idempotently inserts a message, and creates delivery rows for matching rules.
- `worker.py` sweeps stale `sending` rows, claims due deliveries, and dispatches each delivery with its own database session.
- `GET /api/edge-config` returns endpoint ids and `key_sha256` digests for relay config sync.

## Conventions

- Middleware is pure ASGI only.
- `DATABASE_URL` must point to PostgreSQL and is rewritten to `postgresql+asyncpg://`.
- Tables are reflected from the migrated schema; there are no ORM model classes.
- Channel configs stay encrypted except at validation/dispatch boundaries.
- API responses emit dashed UUID strings; ingest accepts dashed UUID and dashless hex ids.
- Password recovery is the `herald-backend reset-password <email>` CLI.

## Commands

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
uv run --project backend --locked pytest backend/tests -v
```

## Do Not

- Do not disable SSRF enforcement.
- Do not use `BaseHTTPMiddleware`.
- Do not log auth headers, ingest keys, passwords, or decrypted channel configs.
- Do not bypass token hashing, encryption, or redaction helpers.
