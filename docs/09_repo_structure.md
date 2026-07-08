# Repo Structure

```text
herald/
├── backend/                 # FastAPI backend, migrations, worker
├── frontend/                # React/Vite dashboard
├── edge/
│   ├── shared/              # relay protocol helpers
│   ├── cloudflare/          # Worker + Durable Object
│   ├── edgeone/             # Pages function + build helper
│   └── tests/               # node:test suite
├── docs/                    # markdown specs + OpenAPI
├── scripts/                 # sync/backup/version helpers
├── docker-compose.yml       # production compose
├── docker-compose.dev.yml   # development compose
└── start.sh                 # local helper
```

## Boundaries

- Backend owns durable storage, rule semantics, provider dispatch, and machine config export.
- Frontend owns browser UX only.
- Edge owns ingress relay behavior only.

## Startup

- `docker compose up` runs production-posture backend services.
- `docker compose -f docker-compose.dev.yml up` runs a local development stack.
- `./start.sh full` runs local PostgreSQL, backend, and Vite with helper ports.
