# AGENTS.md

**Generated:** 2026-03-12 **Commit:** bd9979c **Branch:** main

## Overview

Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, MQTT, or Gotify via user-defined rules. This root repo is the coordination layer around three submodules plus the production FastAPI backend.

## Structure

```text
herald/
├── backend/        # Production FastAPI backend (async PostgreSQL + structlog)
├── frontend/       # React 19 + Vite + React Router dashboard
├── edge/           # Cloudflare Worker lite mode (KV config, HTTP dispatch)
├── docs/           # Product, architecture, data model, API, security, ops
├── .github/        # Docker image builds and cleanup workflows
├── docker-compose.yml # Local dev orchestration (FastAPI + PostgreSQL + worker)
├── start.sh        # Local startup helper (headless|full)
└── .gitmodules     # Submodule remotes and tracked branches
```

Git submodules: `backend/`, `frontend/`, and `edge/` each track their own `main` branch and dependency tree.

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Auth and user lifecycle | `backend/routes/auth.py`, `backend/services/auth.py` | JWT access/refresh lifecycle and account management |
| Ingest endpoint | `backend/routes/ingest.py` | JSON-only, `body` required, 1 MB limit, dashed or dashless UUID |
| Resource API | `backend/routes/`, `backend/services/` | Messages, channels, rules, ingest endpoints |
| Delivery worker | `backend/worker.py` | Async delivery loop with exponential backoff |
| FastAPI backend | `backend/` | Production-ready async stack |
| Structured logging | `backend/logging_config.py` | structlog setup with JSON/console output |
| Error handling | `backend/errors.py` | Global exception handlers |
| Docker | `backend/Dockerfile`, `docker-compose.yml` | Container builds and local dev |
| Frontend auth and routing | `frontend/src/lib/auth.tsx`, `frontend/src/router.tsx` | `sessionStorage` refresh token, BrowserRouter route tree |
| Frontend API URLs | `frontend/src/lib/api.ts`, `frontend/src/lib/public-api.ts` | Direct browser-to-backend calls via `VITE_API_URL` |
| Edge lite runtime | `edge/src/lite.mjs` | KV config, local rule eval, Bark/ntfy dispatch |
| API schema and docs | `docs/openapi.yaml`, `docs/`, `docs/AGENTS.md` | OpenAPI plus markdown specs/runbooks |
| CI/CD | `.github/workflows/` | arm64 Docker builds, workflow/package cleanup |

## Package Communication

```text
Frontend browser --VITE_API_URL--> Backend /api/*
Backend ingest -> DB Message + Delivery rows -> async worker -> Bark/ntfy/MQTT/Gotify
Backend /api/edge-config -> exported snapshot -> Cloudflare KV EDGE_CONFIG
Edge lite -> local rule eval -> Bark/ntfy HTTP dispatch only
```

Production runtime traffic flows through the FastAPI backend (`backend/`), frontend, and edge.

## Conventions

- Backend prefers custom implementations over helper libraries: JWT auth, CORS middleware, `.env` loading, and `DATABASE_URL` parsing are all in-repo.
- PostgreSQL is the only supported database for the backend. `DATABASE_URL` configures the connection via asyncpg with optional pool settings.
- All model primary keys are UUID v4.
- Soft-delete uses nullable timestamps: `deleted_at`, `revoked_at`, `disabled_at`.
- Channel configs are encrypted at rest in `config_json_encrypted`.
- Ingest accepts both dashed UUID and dashless hex endpoint IDs.
- Frontend forms currently use plain React state; `react-hook-form` and `zod` are installed but unused.
- Vite proxies `/api`, `/health`, and `/admin` to the backend in local dev, but production still uses direct browser-to-backend requests via `VITE_API_URL`.

## Anti-Patterns (Do Not)

- Never disable backend SSRF checks in `backend/core/ssrf.py`.
- Never log or commit secrets: `.env`, ingest keys, device keys, access tokens, passwords.
- Never move auth tokens into `localStorage`; refresh stays in `sessionStorage`, access stays in memory.
- Never render ingested content with `dangerouslySetInnerHTML`.
- Never assume edge-lite has the same safety or durability guarantees as the backend worker.
- Never suppress type errors with `as any`, `@ts-ignore`, or `@ts-expect-error`.

## Commands

```bash
# Whole repo
./start.sh headless   # backend only
./start.sh full       # backend + frontend

# Backend (from repo root)
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8001
python -m backend.worker
python -m pytest backend/tests/ -v

# Docker Compose
docker compose up

# Frontend (from frontend/)
pnpm install
pnpm lint
pnpm build
pnpm dev

# Edge (from edge/)
npm install
npm test
npm run lint
npm run dev
```

## Notes

- Backend health endpoint is `GET /health`; edge-lite health endpoint is `GET /healthz`.
- `start.sh` creates the backend virtualenv on demand and can launch frontend dev with matching `APP_BASE_URL` and `CORS_ALLOWED_ORIGINS`.
- Edge-lite currently compares `X-Herald-Ingest-Key` directly against exported `token_hash` values in KV config; document that caveat accurately whenever editing edge docs.
