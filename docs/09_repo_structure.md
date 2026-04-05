# Repo Structure

## Layout

```text
herald/
├── backend/                 # FastAPI backend + async worker
├── frontend/                # React/Vite dashboard
├── edge/                    # Cloudflare lite worker
├── docs/                    # maintained markdown specs + OpenAPI
├── .github/workflows/       # Docker builds and cleanup automation
├── docker-compose.yml       # local API/DB/worker orchestration
├── start.sh                 # local startup helper (backend or backend+frontend)
└── AGENTS.md                # root repo guidance
```

## Monorepo Conventions

- `backend`, `frontend`, and `edge` are first-class directories in this repository.
- The packages are versioned together in one checkout.
- Root repo owns shared documentation, orchestration, and CI/CD wiring.
- `docs/` is part of the root repo.

## Documentation Surfaces

- Package-local guidance lives in `AGENTS.md` files.
- Maintained specs live under `docs/`.
- Repo-facing quick-start docs live in `README.md`, `backend/README.md`, `frontend/README.md`, and `edge/README.md`.

## Startup

- `docker compose up` runs backend + PostgreSQL + worker using the package/container defaults (`5432` / `8000`).
- `./start.sh headless` runs PostgreSQL + backend using helper defaults (`35432` / `38000`).
- `./start.sh full` runs backend + frontend using helper defaults (`35432` / `38000` / `35173`).

## Current Package Boundaries

- `backend/` owns persistent storage, auth, rule matching, delivery worker, and provider integrations (Bark, ntfy, MQTT, Gotify).
- `frontend/` owns browser UI only; it does not proxy backend requests in production.
- `edge/` owns optional best-effort Bark/ntfy fanout from a KV snapshot.
