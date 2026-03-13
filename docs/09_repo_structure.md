# Repo Structure

## Layout

```text
herald/
├── backend/                 # git submodule: FastAPI backend + async worker
├── frontend/                # git submodule: React/Vite dashboard
├── edge/                    # git submodule: Cloudflare lite worker
├── docs/                    # maintained markdown specs + OpenAPI
├── .github/workflows/       # Docker builds and cleanup automation
├── docker-compose.yml       # local API/DB/worker orchestration
├── start.sh                 # local startup helper (backend or backend+frontend)
├── AGENTS.md                # root repo guidance
└── .gitmodules              # submodule remotes and tracked branches
```

## Submodule Conventions

- `backend`, `frontend`, and `edge` are separate repositories mounted as git submodules.
- Each submodule tracks its own `main` branch in `.gitmodules`.
- Root repo owns shared documentation, orchestration, and CI/CD wiring.

## Documentation Surfaces

- Package-local guidance lives in `AGENTS.md` files.
- Maintained specs live under `docs/`.
- Repo-facing quick-start docs live in `README.md`, `backend/README.md`, and `edge/README.md`.

## Startup

- `docker compose up` runs backend + PostgreSQL + worker.
- `./start.sh headless` runs backend only.
- `./start.sh full` runs backend + frontend.

## Current Package Boundaries

- `backend/` owns persistent storage, auth, rule matching, delivery worker, and provider integrations (Bark, ntfy, MQTT, Gotify).
- `frontend/` owns browser UI only; it does not proxy backend requests in production.
- `edge/` owns optional best-effort Bark/ntfy fanout from a KV snapshot.
