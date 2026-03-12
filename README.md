# Herald

Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, or MQTT via user-defined rules.

This repository is the coordination layer around three git submodules:

- `backend/` - Django 5.2 + DRF API + polling delivery worker
- `frontend/` - React 19 + Vite + React Router dashboard
- `edge/` - Cloudflare Worker lite mode (KV config, local rule eval, HTTP dispatch)

## Current Feature Set

- Email/password signup, login, refresh, verification, password reset, change email/password, delete account
- Multiple ingest endpoints per user with token-based auth
- Structured JSON ingest with `body` required and optional `title`, `group`, `priority`, `tags`, `url`, `extras`
- Message history with filters, detail view, soft delete, and batch delete
- Channel types: Bark, ntfy, MQTT
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
- `docs/09_repo_structure.md` - repo/submodule conventions
- `docs/10_edge.md` - current Cloudflare lite runtime
- `docs/11_edge_lite_feasibility.md` - edge-lite tradeoffs and scope boundaries

## Quick Start

Initialize submodules first:

```bash
git submodule update --init --recursive
```

Run backend only:

```bash
./start.sh headless
```

Run backend + frontend:

```bash
./start.sh full
```

Manual package commands live in `docs/07_operations.md` and the package `AGENTS.md` files.
