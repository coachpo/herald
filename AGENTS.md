# AGENTS.md

## Overview

Herald ingests structured JSON over HTTP, stores messages, and forwards them to Bark, ntfy, MQTT, or Gotify. The monorepo contains `backend/`, `frontend/`, `edge/`, docs, scripts, and local orchestration.

## Structure

```text
herald/
├── backend/            # FastAPI backend, migrations, worker
├── frontend/           # React 19 + Vite dashboard
├── edge/               # shared relay code, Cloudflare Worker, EdgeOne Pages function
├── docs/               # specs and operations docs
├── scripts/            # sync, backup, version helpers
├── docker-compose.yml
├── docker-compose.dev.yml
└── start.sh
```

## Where To Look

| Task | Location |
| --- | --- |
| Backend runtime | `backend/cli.py`, `backend/main.py`, `backend/app.py` |
| SQL migrations | `backend/migrations/`, `backend/migrate.py` |
| Auth | `backend/routes/auth.py`, `backend/services/auth.py` |
| Ingest | `backend/routes/ingest.py`, `backend/services/ingest.py` |
| Delivery worker | `backend/worker.py`, `backend/channel_dispatch.py` |
| Edge config export | `backend/routes/edge_config.py`, `backend/edge_config.py` |
| Frontend routes | `frontend/src/router.tsx` |
| Edge relay | `edge/shared/`, `edge/cloudflare/`, `edge/edgeone/` |

## Communication

```text
Frontend -> Backend /api/*
Backend ingest -> messages + deliveries -> worker -> providers
Backend /api/edge-config -> sync script -> relay /admin/config
EdgeOne -> Cloudflare -> Backend
Cloudflare -> Backend
```

## Conventions

- Keep package-specific guidance in child `AGENTS.md` files.
- Use `python -m backend.migrate` for schema setup.
- `start.sh` uses development compose and helper ports `35432`, `38000`, and `35173`.
- Production compose runs `db`, `migrate`, `api`, and `worker`; it does not run frontend or edge.
- Root image CI builds backend and frontend for `linux/amd64,linux/arm64`.
- Edge deployment is explicit and package-local.

## Do Not

- Do not disable SSRF checks in `backend/core/ssrf.py`.
- Do not log or commit secrets.
- Do not store auth tokens in `localStorage`.
- Do not add `as any`, `@ts-ignore`, or `@ts-expect-error`.

## Commands

```bash
./start.sh --help
./start.sh headless
./start.sh full
docker compose up

uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
uv run --project backend --locked pytest backend/tests -v

corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build

npm --prefix edge test
npm --prefix edge run lint
```
