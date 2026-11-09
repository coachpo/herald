# Operations

This guide owns development commands, deployment prerequisites, and operator procedures. It describes the checked-in configuration, not a verified live deployment. All commands below run from the repository root unless another working directory is stated. Relay-specific provisioning and protocol are in [Edge Relay](10_edge.md).

## Processes

- `api`: FastAPI backend, `GET /health`, `/api/*`
- `worker`: async delivery loop, `python -m backend.worker`
- `db`: PostgreSQL 16
- `frontend`: Vite in development or static SPA server on port `3100`
- `edge`: Cloudflare Worker relay and EdgeOne Pages relay

## Local Development

Choose one startup path rather than running the helper and the full development Compose stack together. The helper needs Docker Compose, Python 3.13+, `uv`, `lsof`, and `pgrep`; it looks for `python3.13` first, then `python3` (which must be 3.13+). `full` also needs Node.js 24 and `pnpm` 10.30.1 on `PATH`.

```bash
# Helper: choose headless OR full.
./start.sh headless
./start.sh full
# Alternative: run the backend stack entirely in containers.
docker compose -f docker-compose.dev.yml up
```

`start.sh` uses `DB_PORT=35432`, `BACKEND_PORT=38000`, and `FRONTEND_PORT=35173` by default. Before starting, it recreates the development `db` container (retaining its volume), stops containers bound to these ports, and terminates their listeners—even the frontend port in headless mode. Use it only when those ports are safe to reclaim, or override the helper's three port variables. On exit it stops its database and managed API/Vite processes.

`./start.sh full` starts PostgreSQL, the API, and Vite; `headless` omits Vite. **Neither starts the delivery worker.** To exercise provider delivery, run the worker in another terminal against the helper database, with the same secret/encryption settings as the API:

```bash
DATABASE_URL=postgresql://herald:herald@127.0.0.1:35432/herald_dev \
  uv run --project backend --locked python -m backend.worker
```

Adjust `35432` if `DB_PORT` was overridden. Stop this separately started worker before stopping or restarting the helper. `docker compose -f docker-compose.dev.yml up` instead runs `db`, one-shot `migrate`, `api`, and `worker`; it publishes PostgreSQL on `${POSTGRES_PORT:-5432}` and the API on `8000`, but does not run the frontend. When adding Vite separately, set `VITE_API_URL=http://localhost:8000` and allow its actual origin with `CORS_ALLOWED_ORIGINS` for the API. Development Compose defaults CORS to `http://localhost:3000`, matching this repository's Vite configuration; update CORS if Vite uses a different origin.

For manual backend startup, first provision a reachable PostgreSQL database and export `DATABASE_URL`. The migration CLI reads it directly and does not load an env file. Export the required secret settings too, or put them in `backend/.env` for the API and worker:

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
# Separate terminal, same database and settings:
uv run --project backend --locked python -m backend.worker
```

Backend tests migrate and **truncate all application tables** in `TEST_DATABASE_URL` before each test; never point them at a database whose contents must survive. They default to `postgresql://herald:herald@127.0.0.1:5432/herald`. For an isolated disposable test database, choose a free port and create the container once:

```bash
docker run -d --name herald-test-pg -e POSTGRES_DB=herald -e POSTGRES_USER=herald \
  -e POSTGRES_PASSWORD=herald -p 127.0.0.1:35433:5432 postgres:16-alpine
# Wait until pg_isready succeeds before pytest.
docker exec herald-test-pg pg_isready -U herald -d herald
TEST_DATABASE_URL=postgresql://herald:herald@127.0.0.1:35433/herald \
  uv run --project backend --locked pytest backend/tests -v
```

On later runs, start the same test container only if its database and port mapping match this example. It is independent of the helper's development database.

Frontend commands (Node.js 24, Corepack available):

```bash
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
VITE_API_URL=http://localhost:8000 corepack pnpm@10.30.1 --dir frontend dev
corepack pnpm@10.30.1 --dir frontend preview
```

Set API CORS to the Vite/preview origin before browser testing. Frontend verification is lint and build; no frontend test runner is configured.

Edge commands (Node.js 24):

```bash
npm --prefix edge ci
npm --prefix edge test
npm --prefix edge run lint
```

The edge test command rebuilds the generated EdgeOne shared-module copy before running Node tests. To check version metadata without starting services, run `python3 scripts/sync_version.py --check`. CI defines package checks in [ci.yml](../.github/workflows/ci.yml); choose checks for the affected package rather than starting the whole application for documentation-only changes.

## Production Compose

For an authorized deployment, create a root `.env` from the template only if one does not already exist. Set real secrets before starting the production stack:

```bash
test -e .env || cp .env.example .env
chmod 600 .env
# edit POSTGRES_PASSWORD, SECRET_KEY, and CHANNEL_CONFIG_ENCRYPTION_KEY
docker compose up -d --build
```

Docker Compose reads the root `.env` for interpolation; it passes only variables declared in the Compose service's `environment` block to containers. Adding an arbitrary backend variable to `.env` alone does not configure a container: use an explicit Compose override for additional settings, and recreate affected services. Direct API/worker commands load `backend/.env`, not the root `.env`; the migration CLI requires exported `DATABASE_URL`, and standalone edge config sync requires exported tokens.

`docker-compose.yml` builds the backend locally and runs `db`, one-shot `migrate`, `api`, and `worker`. API and worker wait for a healthy database and successful migration. If migration fails, inspect `docker compose logs migrate`, resolve the failure, and rerun the stack rather than bypassing the dependency. Compose does not publish the database port and does not run frontend or edge deployments. `EDGE_SYNC_TOKEN` is optional; when unset, `/api/edge-config` returns `404`. The database password is interpolated into a connection URL, so use a URL-safe password with this unmodified Compose example.

Root image CI builds only the backend for `linux/amd64,linux/arm64`; eligible main/tag pushes publish it to GHCR. It does not deploy services or publish a frontend/edge image; see [docker-images.yml](../.github/workflows/docker-images.yml).

The `api` service listens on plain HTTP `:8000`. In production, terminate TLS with any reverse proxy (Caddy, nginx, or Cloudflare) in front of it, then:

- point the proxy at `http://<host>:8000`,
- set `FORWARDED_ALLOW_IPS` to the proxy's IP so client IPs and rate limits are honored,
- set `CORS_ALLOWED_ORIGINS` to the dashboard's origin.

Generate a Fernet key:

```bash
uv run --project backend --locked python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## Frontend (production)

Build the static dashboard with the public backend URL baked in:

```bash
docker build -t herald-frontend --build-arg VITE_API_URL=https://api.example.com ./frontend
docker run -d --restart unless-stopped -p 3100:3100 herald-frontend
```

The container exposes port `3100` and serves `/health` for probes. Put it behind your reverse proxy or CDN in production.

## Environment

| Variable | Scope | Notes |
| --- | --- | --- |
| `DATABASE_URL` | backend | PostgreSQL URL; converted to `postgresql+asyncpg://` internally |
| `TEST_DATABASE_URL` | backend tests | PostgreSQL URL used by pytest; defaults to `postgresql://herald:herald@127.0.0.1:5432/herald` |
| `APP_ENV` | backend | `development` or `production`; production rejects default secrets |
| `APP_VERSION` | backend | Optional version override for `/health` |
| `SECRET_KEY` | backend | HMAC and JWT fallback key |
| `JWT_SIGNING_KEY` | backend | Optional JWT signing override |
| `JWT_ACCESS_TTL_SECONDS` | backend | Access-token TTL, default `900` |
| `JWT_REFRESH_TTL_SECONDS` | backend | Refresh-token TTL, default `2592000` |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | backend | Required in production |
| `EDGE_SYNC_TOKEN` | backend/scripts | Enables `GET /api/edge-config` |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated browser origins |
| `FORWARDED_ALLOW_IPS` | backend | Trusted proxy IPs passed to uvicorn. Set this when the API is behind a reverse proxy; otherwise rate limits key on the proxy IP and every sender shares one bucket. |
| `RATE_LIMIT_INGEST_PER_MINUTE` | backend | Ingest token bucket limit, default `120` |
| `RATE_LIMIT_AUTH_PER_MINUTE` | backend | Auth token bucket limit, default `10` |
| `ALLOW_USER_SIGNUP` | backend | Set false after initial user creation if desired |
| `WORKER_POLL_SECONDS` | worker | Sleep when no full batch is claimed, default `1.0` |
| `WORKER_BATCH_SIZE` | worker | Claim batch size, default `50` |
| `DELIVERY_MAX_ATTEMPTS` | worker | Terminal failure threshold, default `10` |
| `DELIVERY_BACKOFF_BASE_SECONDS` | worker | Retry backoff base, default `5` |
| `DELIVERY_BACKOFF_MAX_SECONDS` | worker | Retry backoff cap, default `1800` |
| `DB_POOL_SIZE` | backend/worker | SQLAlchemy pool size, default `5` |
| `DB_MAX_OVERFLOW` | backend/worker | SQLAlchemy overflow, default `10` |
| `DB_POOL_RECYCLE` | backend/worker | SQLAlchemy recycle seconds, default `3600` |
| `DB_POOL_CLASS` | backend/worker | Set `null` to use `NullPool` |
| `LOG_LEVEL` | backend/worker | Default `INFO` |
| `LOG_FORMAT` | backend/worker | `json` or `console` |
| `SENTRY_DSN` | backend/worker | Enables Sentry |
| `SENTRY_TRACES_SAMPLE_RATE` | backend/worker | Default `0.1` |
| `SENTRY_ENVIRONMENT` | backend/worker | Default `production` |
| `BACKEND_HOST` | backend CLI | Default bind host `0.0.0.0` |
| `BACKEND_PORT` / `PORT` | backend CLI | Default port `8000` |
| `WEB_CONCURRENCY` | backend CLI | Default uvicorn workers `2` |
| `MQTT_BLOCK_PRIVATE_NETWORKS` | worker | Dispatch-time MQTT private-network guard, default on; channel validation still enforces SSRF checks |
| `MQTT_SOCKET_TIMEOUT_SECONDS` | worker | MQTT socket timeout, default `5.0` |
| `VITE_API_URL` | frontend | Backend base URL baked into the frontend build and used by browser API calls |
| `RELAY_ADMIN_TOKEN` | edge/scripts/GitHub | Protects relay admin endpoints |
| `UPSTREAM_URL` | edge | Fixed next-hop origin chosen by the operator; intended topology and alternatives are in [Edge Relay](10_edge.md) |

## Admin Tasks

Run migrations against an explicitly configured target database. For a local checkout, export its raw PostgreSQL `DATABASE_URL` in the invoking shell first:

```bash
uv run --project backend --locked python -m backend.migrate
```

For production Compose, use its one-shot `migrate` service (`docker compose run --rm migrate`) with the existing production environment, rather than a local command that may read different settings. Take a backup and coordinate writers before schema maintenance that requires it; startup already gates API/worker on successful migration.

Reset a password without email:

```bash
docker compose exec api herald-backend reset-password user@example.com
```

For local development with a reachable `DATABASE_URL`:

```bash
uv run --project backend --locked herald-backend reset-password user@example.com
```

An operator can install this cron entry after checking Docker access, `PATH`, disk capacity, and the destination's permissions; the repository does not install a backup schedule:

```cron
0 3 * * * BACKUP_DIR=/var/backups/herald /path/to/herald/scripts/backup_db.sh
```

`scripts/backup_db.sh` runs `docker compose exec -T db pg_dump -U herald herald` from the repo root, writes `herald-<timestamp>.sql.gz.tmp`, renames it only after the dump/gzip pipeline succeeds, and deletes `herald-*.sql.gz` files older than `KEEP_DAYS` (default `14`) plus temporary dumps older than one day. `BACKUP_DIR` defaults to repository-local `backups/`; `COMPOSE_DB_SERVICE` can change the service name. The root `.env` used for Compose startup also covers cron. These are script defaults, not an established retention obligation. Dumps contain application data and encrypted channel configs; keep the encryption key and required secrets recoverable separately, and restrict backup access.

For restore, the operator must choose and verify the target before loading data. The plain SQL dump includes schema creation, so it is not an in-place merge into an already initialized database. Stop all writers (including any API/worker instances outside this Compose project), preserve the current database, and prepare an empty replacement target before the load. For the Compose `herald` database, **only after it has been prepared empty**:

```bash
docker compose stop api worker
set -o pipefail
gunzip -c backups/herald-<timestamp>.sql.gz | docker compose exec -T db psql -v ON_ERROR_STOP=1 -U herald herald
```

If decompression or SQL loading fails, leave writers stopped, inspect the error, and prepare a fresh empty target before retrying; do not continue a partial restore. After a successful load, run the version's migrations with the same production settings, verify restored data and key availability, then `docker compose start api worker` and check health. Preparing or replacing the database is deliberately not automated by this example.

Sync edge relay config after endpoint/user changes or relay provisioning. Use the project's Python 3.13+ interpreter for `python3` below (the script's type syntax requires at least 3.10). Export both tokens in the invoking shell; root `.env` is not read by this Python script:

```bash
EDGE_SYNC_TOKEN="$EDGE_SYNC_TOKEN" RELAY_ADMIN_TOKEN="$RELAY_ADMIN_TOKEN" \
  python3 scripts/sync_edge_config.py \
    --backend https://backend.example.com \
    --edges https://cf.example.workers.dev,https://edge.example.cn
```

Follow [config sync and failure handling](10_edge.md#config). If any relay update fails, the script exits nonzero after attempting all relays; fix it and retry rather than assuming they are consistent. The checked-in EdgeOne drain workflow is manual, not scheduled; see [Drain Fallback](10_edge.md#drain-fallback).

## Health

- Backend: `GET /health`, returns `503` when the database check fails.
- Frontend static server: `GET /health` checks the server, not backend reachability.
- Cloudflare and EdgeOne relays: `GET /healthz` checks liveness, not config, storage, or upstream health. Use authenticated `/admin/status` to inspect backlog and config version.
