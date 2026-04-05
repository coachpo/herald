# Herald

Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, MQTT, or Gotify via user-defined rules.

This repository is a monorepo containing three first-class packages:

- `backend/` - Production FastAPI backend with async PostgreSQL, structured logging, and Docker support
- `frontend/` - React 19 + Vite + React Router dashboard
- `edge/` - Cloudflare Worker lite mode (KV config, local rule eval, HTTP dispatch)

## Current Feature Set

- Email/password signup, login, refresh, verification, password reset, change email/password, delete account
- Multiple ingest endpoints per user with token-based auth
- Structured JSON ingest with `body` required and optional `title`, `group`, `priority`, `tags`, `url`, `extras`
- Message history with filters, detail view, soft delete, and batch delete
- Channel types: Bark, ntfy, MQTT, Gotify
- Forwarding rules with endpoint/body/priority/tag/group filters and Mustache-style payload templates
- Background delivery worker with exponential backoff retries
- Edge-lite mode for Bark/ntfy HTTP fanout from Cloudflare Workers

## Repository Layout

```text
herald/
├── backend/
├── frontend/
├── edge/
├── docs/
├── .github/workflows/
├── docker-compose.yml
└── start.sh
```

## Docs

- `docs/01_prd.md` - product scope and user-facing behavior
- `docs/02_architecture.md` - runtime architecture and package communication
- `docs/03_data_model.md` - backend entities and stored fields
- `docs/04_api_spec.md` - human-readable API guide
- `docs/openapi.yaml` - API schema source of truth
- `docs/05_ui_spec.md` - implemented dashboard routes and pages
- `docs/06_security_privacy.md` - tokens, SSRF, redaction, safety constraints
- `docs/07_operations.md` - env vars, deploy/runtime notes, health endpoints
- `docs/08_bark_v2.md` - Bark-specific provider behavior
- `docs/09_repo_structure.md` - repo layout and package boundaries
- `docs/10_edge.md` - current Cloudflare lite runtime
- `docs/11_edge_lite_feasibility.md` - edge-lite tradeoffs and scope boundaries

## Versioning

`VERSION` at the repo root is the monorepo version source of truth.

When you bump the release version, keep these files aligned with it:

- `backend/pyproject.toml`
- `frontend/package.json`
- `edge/package.json`

The backend health/version response prefers explicit `APP_VERSION`, then installed package metadata, then falls back to the repo `VERSION` file so local checkouts and CI stay aligned with the monorepo release value.

## Quick Start

Clone the repo once; `backend/`, `frontend/`, and `edge/` are part of the same checkout.

### FastAPI Backend (recommended)

```bash
# With Docker Compose (from repo root)
docker compose up

# Manual (from repo root, Python 3.13+)
uv sync --project backend --locked
uv run --project backend --locked python backend/bootstrap_dev_db.py
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
```

`backend/uv.lock` is committed. Refresh it with `uv lock --project backend` when you intentionally change backend dependency metadata.

### Local Helper Script

```bash
./start.sh headless   # backend only
./start.sh full       # backend + frontend
```

Manual package commands live in `docs/07_operations.md` and the package `AGENTS.md` files.

## CI/CD

- `.github/workflows/ci.yml` validates version alignment, provisions PostgreSQL for backend tests, bootstraps the backend schema, then runs backend tests, frontend lint/build, and edge test/lint on pushes and pull requests.
- `.github/workflows/docker-images.yml` builds and publishes backend/frontend arm64 container images.
- `.github/workflows/cleanup.yml` prunes old workflow runs and untagged container images.

The local commands in this README mirror the package checks used by CI.
