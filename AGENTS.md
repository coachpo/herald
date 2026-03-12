# AGENTS.md

**Generated:** 2026-03-12 **Commit:** bd9979c **Branch:** main

## Overview

Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, or MQTT via user-defined rules. This root repo is the coordination layer around three submodules: Django backend, React/Vite frontend, and Cloudflare Worker lite edge.

## Structure

```text
herald/
├── backend/        # Django 5.2 + DRF API + polling delivery worker
├── frontend/       # React 19 + Vite + React Router dashboard
├── edge/           # Cloudflare Worker lite mode (KV config, HTTP dispatch)
├── docs/           # Product, architecture, data model, API, security, ops
├── .github/        # Docker image builds and cleanup workflows
├── start.sh        # Local startup helper (headless|full)
└── .gitmodules     # Submodule remotes and tracked branches
```

Git submodules: `backend/`, `frontend/`, and `edge/` each track their own `main` branch and dependency tree.

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Auth and user lifecycle | `backend/accounts/`, `backend/api/views_auth.py` | Custom user, JWT, refresh rotation, email flows |
| Ingest endpoint | `backend/api/ingest.py` | JSON-only, `body` required, 1 MB limit, dashed or dashless UUID |
| Resource API | `backend/api/views_resources.py`, `backend/api/serializers.py` | Messages, channels, rules, ingest endpoints |
| Delivery worker | `backend/core/management/commands/deliveries_worker.py` | Polling DB queue, exponential backoff |
| Frontend auth and routing | `frontend/src/lib/auth.tsx`, `frontend/src/router.tsx` | `sessionStorage` refresh token, BrowserRouter route tree |
| Frontend API URLs | `frontend/src/lib/api.ts`, `frontend/src/lib/public-api.ts` | Direct browser-to-backend calls via `VITE_API_URL` |
| Edge lite runtime | `edge/src/lite.mjs` | KV config, local rule eval, Bark/ntfy dispatch |
| API schema and docs | `docs/openapi.yaml`, `docs/`, `docs/AGENTS.md` | OpenAPI plus markdown specs/runbooks |
| CI/CD | `.github/workflows/` | arm64 Docker builds, workflow/package cleanup |

## Package Communication

```text
Frontend browser --VITE_API_URL--> Backend /api/*
Backend ingest -> DB Message + Delivery rows -> polling worker -> Bark/ntfy/MQTT
Backend /api/edge-config -> exported snapshot -> Cloudflare KV EDGE_CONFIG
Edge lite -> local rule eval -> Bark/ntfy HTTP dispatch only
```

No shared runtime code crosses package boundaries; synchronization happens through JSON APIs, the database, and KV snapshots.

## Conventions

- Backend prefers custom implementations over helper libraries: JWT auth, CORS middleware, and `.env` loading are all in-repo.
- SQLite is the default runtime database in this repo; `DATABASE_URL` parsing exists, but no Postgres driver is installed here.
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

# Backend (from backend/)
python manage.py migrate --noinput
python manage.py test
python manage.py runserver 0.0.0.0:8000
python manage.py deliveries_worker

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
- `start.sh` creates the backend virtualenv on demand, runs migrations, and can launch frontend dev with matching `APP_BASE_URL` and `CORS_ALLOWED_ORIGINS`.
- Edge-lite currently compares `X-Herald-Ingest-Key` directly against exported `token_hash` values in KV config; document that caveat accurately whenever editing edge docs.
