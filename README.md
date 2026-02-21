# Beacon Spear (Design Docs)

Beacon Spear is a small web app for ingesting arbitrary UTF-8 message payloads, storing them, and forwarding them via user-defined rules to notification channels (Bark v2 only in v0.1).

This repository contains design documents and an initial v0.1 implementation.

Implementation lives in **git submodules**:

- `backend/` — Django backend + worker
- `frontend/` — React 19 + Vite dashboard

## Scope (v0.1)

- Self-signup (email + password) with **email verification**
- Password reset via email (SMTP)
- Per-user **multiple ingest endpoints** (token-based)
- Ingest accepts **any** request body as **UTF-8 string**, **no validation**, **max 1MB** (reject oversize)
- Store ingested messages in DB with request metadata (headers/query/ip/ua), with sensitive header redaction
- Message list/detail + delete (single + batch delete “older than N days”)
- Forwarding rules (CRUD): simple matching on `ingest_endpoint_id` and/or `payload_text`
- One rule forwards to one channel; execute all matching rules; duplicates allowed
- Channels: Bark (API v2) only; supports any Bark server; “mirror Bark fields” in UI
- Delivery worker with at-least-once semantics and exponential backoff retries

## Documents

- `docs/01_prd.md` — product requirements, user stories, acceptance criteria
- `docs/02_architecture.md` — system architecture and data flows
- `docs/03_data_model.md` — database schema and indexing
- `docs/04_api_spec.md` — HTTP APIs (ingest + app API)
- `docs/openapi.yaml` — OpenAPI 3.1 (JSON API + ingest)
- `docs/05_ui_spec.md` — UI pages and UX behavior
- `docs/06_security_privacy.md` — threat model, redaction, auth, tokens
- `docs/07_operations.md` — configuration, deploy outline, worker ops
- `docs/08_bark_v2.md` — Bark v2 payload + UI mirroring notes
- `docs/09_repo_structure.md` — repo layout and submodule conventions
- `docs/10_edge.md` — edge forwarders (EdgeOne + Cloudflare)

## Open questions (to confirm before implementation)

- Do you want any global admin functions (ban users, view system health), or user-only?
- Should batch delete be soft-delete only, or also provide an irreversible “hard delete”?

Current implementation defaults:
- user-only (no global admin features beyond Django admin)
- soft-delete only

## Local dev (quick)

Backend:

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Worker:

```bash
cd backend
. .venv/bin/activate
python manage.py deliveries_worker
```

Frontend:

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev
```
