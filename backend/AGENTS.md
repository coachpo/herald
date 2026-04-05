# backend/AGENTS.md

## Overview

FastAPI async backend for Herald: auth, ingest, persistent message storage, delivery worker, provider dispatch, and edge snapshot export.

## Structure

```text
backend/
├── auth/          # JWT, refresh/session, password/token helpers
├── core/          # crypto, rules, templates, redaction, SSRF
├── providers/     # Bark, ntfy, MQTT, Gotify delivery code
├── routes/        # HTTP endpoints plus edge-config export
├── services/      # business logic, validation, state transitions
├── tests/         # pytest suite
├── app.py         # FastAPI factory + middleware + health route
├── cli.py         # herald-backend CLI -> uvicorn launcher
├── main.py        # backend.main:app ASGI target
├── bootstrap_dev_db.py # local PostgreSQL schema bootstrap
├── database.py    # async engine + reflected tables
├── worker.py      # retry loop + dispatch orchestration
└── edge_config.py # Cloudflare snapshot export
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| App bootstrap | `cli.py`, `main.py`, `app.py` | `herald-backend` -> uvicorn -> `create_app()`, lifespan, middleware, `/health` |
| Settings and env | `config.py`, `database.py` | Custom `.env` loading, PostgreSQL async engine, reflected Django tables |
| Auth lifecycle | `routes/auth.py`, `routes/auth_*.py`, `auth/`, `services/auth_*.py` | Router aggregator plus signup/login/refresh/change/delete token flows |
| Request and response schemas | `requests.py`, `models.py` | Pydantic write payloads plus API envelopes |
| Ingest endpoint CRUD | `routes/ingest_endpoints.py`, `services/ingest_endpoints.py` | List/create/detail/rename/revoke/archive |
| Public ingest endpoint | `routes/ingest.py` | Token hashing, verified-email gate, JSON validation, message creation, delivery enqueue |
| Channels | `routes/channels.py`, `services/channel_*.py` | List/create/delete, validation, encrypted configs, send-test |
| Rules and templating | `routes/rules.py`, `core/rules.py`, `core/template.py` | Filter matching plus payload rendering and no-send previews |
| Message APIs | `routes/messages.py`, `services/messages.py` | List/detail, soft delete, batch delete, deliveries |
| Worker delivery loop | `worker.py`, `channel_dispatch.py` | Claim due deliveries, retry with backoff, provider dispatch |
| Dev schema bootstrap | `bootstrap_dev_db.py` | Creates the local PostgreSQL tables used by `start.sh` |
| Edge snapshot export | `routes/__init__.py`, `edge_config.py` | Bark/ntfy-only export for `edge/` |
| Security helpers | `core/ssrf.py`, `core/redaction.py`, `core/crypto.py` | SSRF guardrails, header redaction, config encryption |
| Tests | `tests/`, `tests/conftest.py` | Pytest plus env overrides; requires PostgreSQL |

## Runtime Flow

- `POST /api/ingest/{endpoint_id}` hashes the ingest key, requires a verified active user, validates JSON plus size/type constraints, stores the message, and enqueues matching deliveries.
- `worker.py` claims queued or retry rows with `FOR UPDATE SKIP LOCKED`, decrypts channel config, dispatches the provider, and records `sent`, `retry`, or `failed`.
- `GET /api/edge-config` exports active ingest endpoints plus enabled Bark/ntfy channels and rules with a version hash for KV snapshots.
- `GET /health` returns `200` with `status: ok` when the database is reachable or `503` with `status: degraded` when it is not.

## Conventions

- Middleware is pure ASGI only; `middleware.py` documents why `BaseHTTPMiddleware` breaks asyncpg task affinity.
- `herald-backend` resolves host/port/workers from CLI args with env fallbacks in `cli.py`; `main.py` stays a thin ASGI target for uvicorn.
- Database access uses SQLAlchemy async reflection over existing Django table names; do not assume declarative ORM models or SQLite support.
- `DATABASE_URL` must be PostgreSQL and is rewritten to `postgresql+asyncpg://`.
- Channel configs live encrypted in `config_json_encrypted`; decrypt only at the service, dispatch, or edge-export boundary.
- Soft delete and revocation use nullable timestamps: `deleted_at`, `revoked_at`, `disabled_at`.
- API responses emit dashed UUID strings, but ingest accepts dashed UUID and dashless hex IDs.
- `GET /messages` currently honors `ingest_endpoint_id`, `priority_min`, `priority_max`, `from`, and `to`; docs should not promise `q`, `group`, or `tag` filters until implemented.
- Channels support list/create/delete/test only; channel creation responses return `{channel, config}`.
- Verification and password-reset request endpoints create hashed DB tokens and log events; outbound email delivery is not implemented in this repo.

## Anti-Patterns

- Do not disable SSRF enforcement in `core/ssrf.py` or bypass provider safety checks.
- Do not use `BaseHTTPMiddleware`; keep request handling in one task.
- Do not log raw auth headers, ingest keys, passwords, or decrypted channel secrets.
- Do not bypass token hashing, config encryption, or header redaction helpers with ad hoc implementations.
- Do not document configurable ingest verification flags, repo-local email sending, unsupported message filters, or channel-detail config unless the implementation changes.
- Do not document edge-lite behavior as backend-equivalent auth, durability, or provider coverage.
- Do not forget that backend tests in `tests/` expect PostgreSQL at `127.0.0.1:5432/herald` unless you override env consistently.

## Commands

```bash
# From repo root
uv sync --project backend --locked
uv run --project backend --locked python backend/bootstrap_dev_db.py
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
uv run --project backend --locked pytest backend/tests/ -v
```

- Backend development expects Python 3.13+ and the committed `backend/uv.lock`; refresh it with `uv lock --project backend` only when dependency metadata changes intentionally.

## Testing

- `tests/conftest.py` injects database, JWT, and encryption env vars for pytest.
- Coverage is split across auth, core, errors, logging, middleware, providers, routes, and services.
