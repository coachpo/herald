# AGENTS.md

**Generated:** 2026-03-18 **Commit:** 1b3d6aa **Branch:** main

## Overview

Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, MQTT, or Gotify via user-defined rules. This root repo coordinates three git submodules (`backend/`, `frontend/`, `edge/`), shared docs, and local orchestration.

## Structure

```text
herald/
├── backend/           # FastAPI backend + async delivery worker
├── frontend/          # React 19 + Vite dashboard
├── edge/              # Cloudflare Worker lite runtime
├── docs/              # Product, architecture, API, security, ops
├── .github/           # GHCR image build + cleanup workflows
├── docker-compose.yml # Local PostgreSQL + API + worker stack
├── start.sh           # Local backend/full startup helper
└── .gitmodules        # Submodule remotes and tracked branches
```

Git submodules: `backend/`, `frontend/`, and `edge/` each track `main`. `docs/` is part of the root repo, not a submodule. Package-local guidance lives in `backend/AGENTS.md`, `frontend/AGENTS.md`, `edge/AGENTS.md`, and `docs/AGENTS.md`.

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Repo/package boundaries | `.gitmodules`, `docs/09_repo_structure.md` | Root repo coordinates submodules, docs, and orchestration |
| Backend package guide | `backend/AGENTS.md`, `backend/README.md` | Auth, ingest, worker, providers, edge export |
| Frontend package guide | `frontend/AGENTS.md`, `frontend/src/router.tsx` | Routes, auth state, API helpers, deploy server |
| Edge package guide | `edge/AGENTS.md`, `edge/src/lite.mjs` | KV snapshot ingest, rule eval, Bark/ntfy dispatch |
| Spec governance | `docs/AGENTS.md`, `docs/openapi.yaml` | Docs index plus schema source of truth |
| Local startup | `start.sh`, `docker-compose.yml` | `start.sh` uses helper ports; compose runs db/api/worker only |
| CI/CD scope | `.github/workflows/docker-images.yml`, `.github/workflows/cleanup.yml` | Root CI builds backend/frontend images only |
| Auth and ingest | `backend/routes/auth.py`, `backend/routes/ingest.py` | JWT lifecycle, verified-email gate, JSON ingest validation |
| Delivery pipeline | `backend/worker.py`, `backend/channel_dispatch.py` | Retry loop plus provider dispatch |
| Edge snapshot export | `backend/edge_config.py`, `edge/src/lite.mjs` | Backend export -> KV snapshot -> edge-lite ingest |
| Frontend auth storage | `frontend/src/lib/auth.tsx`, `frontend/src/lib/public-api.ts` | `sessionStorage` refresh token, access token in memory, ingest URL hex conversion |

## Package Communication

```text
Frontend browser --VITE_API_URL--> Backend /api/*
Backend ingest -> DB Message + Delivery rows -> async worker -> Bark/ntfy/MQTT/Gotify
Backend /api/edge-config -> exported snapshot -> Cloudflare KV EDGE_CONFIG
Edge lite -> local rule eval -> Bark/ntfy HTTP dispatch only
```

## Conventions

- Root `AGENTS.md` covers cross-package coordination; package-local implementation details belong in child `AGENTS.md` files.
- `backend/`, `frontend/`, and `edge/` remain git submodules; update boundaries through `.gitmodules`, not ad hoc copies.
- Production frontend traffic is direct browser-to-backend via `VITE_API_URL`; Vite proxy config is local-dev-only.
- `start.sh` defaults to helper ports `35432` (db), `38000` (backend), and `35173` (frontend) unless env overrides are provided.
- Manual and container examples still use the package defaults (`herald-backend` on `8000`, Vite `3000`, deploy server `3100`); docs should distinguish those from `start.sh` helper ports.
- `docker-compose.yml` starts PostgreSQL, API, and worker only; it does not launch frontend or edge.
- Root CI builds and cleans up `backend` and `frontend` arm64 images in GHCR; `edge/` deployment is manual or external to root workflows.

## Anti-Patterns (Do Not)

- Never disable backend SSRF checks in `backend/core/ssrf.py`.
- Never log or commit secrets: `.env`, ingest keys, device keys, access tokens, passwords.
- Never move auth tokens into `localStorage`; refresh stays in `sessionStorage`, access stays in memory.
- Never treat edge-lite as backend-equivalent durability or safety; it is best-effort only and skips backend-style SSRF checks.
- Never assume root CI covers `edge/`; check `edge/` commands or external deployment steps explicitly.
- Never suppress type errors with `as any`, `@ts-ignore`, or `@ts-expect-error`.

## Commands

```bash
# Repo setup
git submodule update --init --recursive

# Whole repo
./start.sh --help
./start.sh headless
./start.sh full
docker compose up

# Backend (from repo root)
python -m pip install -e "backend[test]"
python backend/bootstrap_dev_db.py
python -m pytest backend/tests/ -v
herald-backend
python -m backend.worker

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
npm run deploy
```

## Notes

- Backend health is `GET /health` and returns `200` when the database is connected or `503` with `status: degraded` when it is not.
- Edge-lite health is `GET /healthz`; the frontend deploy server also exposes `GET /health`.
- `docs/openapi.yaml` is the API schema source of truth and should stay aligned with the implemented routes, not older markdown claims.
- Edge-lite currently compares `X-Herald-Ingest-Key` directly against exported `token_hash` values in KV config; docs must describe implemented behavior exactly.
