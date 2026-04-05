# AGENTS.md

**Generated:** 2026-04-05 **Commit:** f60056a **Branch:** main

## Overview

<<<<<<< HEAD
Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, MQTT, or Gotify via user-defined rules. This root repo is a coordination layer around three git submodules plus a root-owned docs tree.

Use this file for repo boundaries, startup and CI scope, and package interaction. Push package internals down into child knowledge bases before editing code.
=======
Herald ingests structured JSON messages over HTTP, stores them, and forwards them to Bark, ntfy, MQTT, or Gotify via user-defined rules. This repository is a monorepo containing `backend/`, `frontend/`, and `edge/`, plus shared docs and local orchestration.
>>>>>>> 0338408 (Record monorepo repo structure updates)

## Structure

```text
herald/
<<<<<<< HEAD
├── backend/                 # FastAPI API, worker, provider dispatch, edge export
│   ├── routes/AGENTS.md     # HTTP contract layer
│   └── services/AGENTS.md   # business logic and state-transition layer
├── frontend/                # React 19 + Vite dashboard
│   └── src/lib/AGENTS.md    # client auth and API-contract helpers
├── edge/                    # Cloudflare Worker lite runtime
│   └── src/AGENTS.md        # worker request/auth/dispatch core
├── docs/                    # root-owned product, API, security, and ops docs
├── .github/workflows/       # backend/frontend image build + cleanup only
├── docker-compose.yml       # db + api + worker stack
├── start.sh                 # helper launcher for db + backend [+ frontend]
└── .gitmodules              # submodule remotes pinned on main
```

`backend/`, `frontend/`, and `edge/` are independent repos pinned by the root superproject. `docs/` lives in the root repo and owns shared spec accuracy.
=======
├── backend/           # FastAPI backend + async delivery worker
├── frontend/          # React 19 + Vite dashboard
├── edge/              # Cloudflare Worker lite runtime
├── docs/              # Product, architecture, API, security, ops
├── .github/           # GHCR image build + cleanup workflows
├── docker-compose.yml # Local PostgreSQL + API + worker stack
└── start.sh           # Local backend/full startup helper
```

`backend/`, `frontend/`, and `edge/` live in this repository and are versioned together. Package-local guidance lives in `backend/AGENTS.md`, `frontend/AGENTS.md`, `edge/AGENTS.md`, and `docs/AGENTS.md`.
>>>>>>> 0338408 (Record monorepo repo structure updates)

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
<<<<<<< HEAD
| Repo boundaries | `.gitmodules`, `docs/09_repo_structure.md` | Backend/frontend/edge are submodules; docs/ is root-owned |
| Root runtime split | `start.sh`, `docker-compose.yml`, `docs/07_operations.md` | Helper script and compose do not start the same services or use the same ports |
| Package interaction map | `docs/02_architecture.md`, `docs/openapi.yaml` | Browser -> backend, backend -> worker, backend -> edge snapshot |
| Backend package guide | `backend/AGENTS.md`, `backend/routes/AGENTS.md`, `backend/services/AGENTS.md` | API, worker, route contracts, service-layer rules |
| Frontend package guide | `frontend/AGENTS.md`, `frontend/src/lib/AGENTS.md` | Router, auth state, API helpers, deploy-vs-dev split |
| Edge package guide | `edge/AGENTS.md`, `edge/src/AGENTS.md` | Worker config, request flow, runtime caveats |
| Docs governance | `docs/AGENTS.md`, `docs/openapi.yaml` | Shared docs precedence and drift policy |
| Root CI scope | `.github/workflows/docker-images.yml`, `.github/workflows/cleanup.yml` | GHCR image build + cleanup for backend/frontend only |

## Code Map

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `main()` | Function | `backend/cli.py` | CLI entry that launches uvicorn |
| `create_app()` | Function | `backend/app.py` | FastAPI factory and backend `/health` owner |
| `router` | Variable | `frontend/src/router.tsx` | Canonical frontend route tree and layout split |
| `handleLiteRequest()` | Function | `edge/src/lite.mjs` | Edge auth, validation, rule, and dispatch orchestration |

## Conventions

- Root guidance is coordination-first. Child AGENTS files own implementation detail.
- Treat submodules as independent repos pinned by the superproject, not as ordinary folders with shared history.
- `git submodule update --init --recursive` is the grounded repo setup command. Do not assume clone alone is ready.
- Production frontend traffic goes directly from the browser to the backend via `VITE_API_URL`; Vite proxying is local-dev-only.
- `start.sh` uses helper ports `35432` (db), `38000` (backend), and `35173` (frontend) unless env overrides are provided.
- `docker compose up` starts PostgreSQL, API, and worker on package defaults; it does not launch frontend or edge.
- `start.sh full` starts PostgreSQL, backend, and frontend, but still does not start the backend worker.
- Backend commands assume Python 3.13+ and the committed `backend/uv.lock`; refresh it with `uv lock --project backend` only when dependency metadata changes intentionally.
- Root CI builds and cleans up backend/frontend arm64 images only. Edge deployment stays package-local and manual or external.

## Anti-Patterns

- Never describe root commands as "starts everything". Name the exact services each path starts and what it omits.
- Never assume process or container startup means the system is ready; distinguish launch from readiness.
- Never assume root CI covers `edge/`; check package-local commands instead.
- Never treat edge-lite as backend-equivalent durability, auth, or SSRF behavior.
- Never log or commit secrets: `.env`, ingest keys, device keys, access tokens, or passwords.
=======
| Repo/package boundaries | `docs/09_repo_structure.md` | Root repo coordinates packages, docs, and orchestration |
| Backend runtime entry | `backend/cli.py`, `backend/main.py`, `backend/app.py` | `herald-backend` CLI -> uvicorn -> FastAPI app factory |
| Backend package guide | `backend/AGENTS.md`, `backend/README.md` | Auth, ingest, worker, providers, edge export |
| Frontend package guide | `frontend/AGENTS.md`, `frontend/src/router.tsx` | Routes, auth state, API helpers, deploy server |
| Frontend deploy entry | `frontend/deploy/server.mjs`, `frontend/package.json` | Built SPA server on `3100`; Vite stays a local-dev tool |
| Edge package guide | `edge/AGENTS.md`, `edge/src/lite.mjs` | KV snapshot ingest, rule eval, Bark/ntfy dispatch |
| Spec governance | `docs/AGENTS.md`, `docs/openapi.yaml` | Docs index plus schema source of truth |
| Local startup | `start.sh`, `docker-compose.yml` | `start.sh` bootstraps db schema plus backend and optional frontend; compose runs db/api/worker |
| CI/CD scope | `.github/workflows/docker-images.yml`, `.github/workflows/cleanup.yml` | Root CI builds backend/frontend arm64 images only; `workflow_dispatch` can target one service |
| Auth and ingest | `backend/routes/auth.py`, `backend/routes/ingest.py` | JWT lifecycle, verified-email gate, JSON ingest validation |
| Delivery pipeline | `backend/worker.py`, `backend/channel_dispatch.py` | Worker retry loop plus provider dispatch; not started by `start.sh` |
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
- `backend/`, `frontend/`, and `edge/` are first-class directories in this monorepo; keep package boundaries documented in `docs/09_repo_structure.md`.
- Production frontend traffic is direct browser-to-backend via `VITE_API_URL`; Vite proxy config is local-dev-only.
- `start.sh` defaults to helper ports `35432` (db), `38000` (backend), and `35173` (frontend) unless env overrides are provided.
- `start.sh` manages PostgreSQL, backend, and optional frontend only; run `docker compose up` or `uv run --project backend --locked python -m backend.worker` when worker behavior matters.
- `frontend/deploy/server.mjs` is the production static server on `3100`; `pnpm dev` remains the local Vite path on `3000`.
- Backend developer commands expect Python 3.13+ and the committed `backend/uv.lock`; refresh it with `uv lock --project backend` only when dependency metadata changes intentionally.
- Manual and container examples still use the package defaults (`herald-backend` on `8000`, Vite `3000`, deploy server `3100`); docs should distinguish those from `start.sh` helper ports.
- `docker-compose.yml` starts PostgreSQL, API, and worker only; it does not launch frontend or edge.
- Root CI builds and cleans up `backend` and `frontend` arm64 images in GHCR; `edge/` deployment is manual or external to root workflows.

## Anti-Patterns (Do Not)

- Never disable backend SSRF checks in `backend/core/ssrf.py`.
- Never log or commit secrets: `.env`, ingest keys, device keys, access tokens, passwords.
>>>>>>> 0338408 (Record monorepo repo structure updates)
- Never move auth tokens into `localStorage`; refresh stays in `sessionStorage`, access stays in memory.
- Never suppress type errors with `as any`, `@ts-ignore`, or `@ts-expect-error`.

## Unique Styles

- Keep command docs paired with working directory and service scope in the same bullet or code block.
- Prefer exact runtime language such as `entrypoint`, `helper`, `best-effort`, and `child guide` over generic monorepo wording.
- Keep root notes short enough that the next action is obvious: descend into the relevant child AGENTS before editing code.

## Commands

```bash
<<<<<<< HEAD
# Repo setup
git submodule update --init --recursive

# Root helper paths
=======
# Whole repo
>>>>>>> 0338408 (Record monorepo repo structure updates)
./start.sh --help
./start.sh headless
./start.sh full
docker compose up

# Backend (from repo root)
uv sync --project backend --locked
uv run --project backend --locked python backend/bootstrap_dev_db.py
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
uv run --project backend --locked pytest backend/tests/ -v

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

<<<<<<< HEAD
- `docker-images.yml` supports `workflow_dispatch` with `all`, `backend`, or `frontend`, and checks out submodules recursively before building images.
- Backend health is `GET /health`; edge health is `GET /healthz`; the frontend deploy server exposes `GET /health` on port `3100`.
- `docs/openapi.yaml` is the shared API schema source of truth when markdown docs drift.
=======
- Backend health is `GET /health` and returns `200` when the database is connected or `503` with `status: degraded` when it is not.
- Backend runtime enters through `backend/cli.py` -> `backend.main:app`; the async worker still runs separately from `python -m backend.worker`.
- Edge-lite health is `GET /healthz`; the frontend deploy server also exposes `GET /health`.
- `docs/openapi.yaml` is the API schema source of truth and should stay aligned with the implemented routes, not older markdown claims.
- Edge-lite currently compares `X-Herald-Ingest-Key` directly against exported `token_hash` values in KV config; docs must describe implemented behavior exactly.
ted `token_hash` values in KV config; docs must describe implemented behavior exactly.
>>>>>>> 0338408 (Record monorepo repo structure updates)
