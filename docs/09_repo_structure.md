# Repo Structure

## Layout

```text
herald/
├── backend/                 # git submodule: Django API + worker
├── frontend/                # git submodule: React/Vite dashboard
├── edge/                    # git submodule: Cloudflare lite worker
├── docs/                    # maintained markdown specs + OpenAPI
├── .github/workflows/       # Docker builds and cleanup automation
├── start.sh                 # local startup helper
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

## Startup Helper

`start.sh` supports two modes:

- `headless` - backend only
- `full` - backend + frontend

In `full` mode it also sets sensible local defaults for `APP_BASE_URL`, `CORS_ALLOWED_ORIGINS`, and `VITE_API_URL`.

## Current Package Boundaries

- Backend owns persistent storage, auth, rule matching, and MQTT.
- Frontend owns browser UI only; it does not proxy backend requests in production.
- Edge owns optional best-effort Bark/ntfy fanout from a KV snapshot.
