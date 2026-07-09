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

## Where To Look

| Task | Location |
| --- | --- |
| App factory and middleware | `app.py`, `middleware.py` |
| Reflected tables and sessions | `database.py` |
| Settings/env validation | `config.py` |
| Dashboard routes | `routes/__init__.py`, `routes/*.py` |
| Auth routes/services | `routes/auth.py`, `services/auth.py`, `auth/` |
| Ingest trust boundary | `routes/ingest.py`, `services/ingest.py` |
| Rule matching/templates | `core/rules.py`, `core/template.py`, `services/rules.py` |
| Delivery dispatch | `worker.py`, `channel_dispatch.py`, `providers/` |
| Edge config export | `routes/__init__.py`, `edge_config.py` |

## Runtime Flow

- `POST /api/ingest/{endpoint_id}` authenticates the raw key, validates JSON, handles relay headers, idempotently inserts a message, and creates delivery rows for matching rules.
- `worker.py` sweeps stale `sending` rows, claims due deliveries, and dispatches each delivery with its own database session.
- `GET /api/edge-config` is declared in `routes/__init__.py`; it returns `version`, `updated_at`, and active endpoint `id` / `key_sha256` pairs for relay config sync.

## Conventions

- Middleware is pure ASGI only.
- `DATABASE_URL` must point to PostgreSQL and is rewritten to `postgresql+asyncpg://`.
- Tables are reflected from the migrated schema; there are no ORM model classes.
- Channel configs stay encrypted except at validation/dispatch boundaries.
- API responses emit dashed UUID strings; ingest accepts dashed UUID and dashless hex ids.
- Password recovery is the `herald-backend reset-password <email>` CLI.
- Service code owns commits/rollbacks; route code maps service exceptions to HTTP responses.
- `database.py`, `config.py`, and `schemas/__init__.py` have high blast radius; check route, service, worker, and tests when changing them.

## Command Notes

- Root `AGENTS.md` carries the normal backend install/run/test commands.
- Password recovery is `uv run --project backend --locked herald-backend reset-password <email>`.
- Tests need PostgreSQL through `TEST_DATABASE_URL`; the default is `postgresql://herald:herald@127.0.0.1:5432/herald`.

## Do Not

- Do not disable SSRF enforcement.
- Do not use `BaseHTTPMiddleware`.
- Do not log auth headers, ingest keys, passwords, or decrypted channel configs.
- Do not bypass token hashing, encryption, or redaction helpers.
