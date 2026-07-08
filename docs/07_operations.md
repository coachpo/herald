# Operations

## Processes

- `api`: FastAPI backend, `GET /health`, `/api/*`
- `worker`: async delivery loop, `python -m backend.worker`
- `db`: PostgreSQL 16
- `frontend`: Vite in development or static SPA server on port `3100`
- `edge`: Cloudflare Worker relay and EdgeOne Pages relay

## Local Development

```bash
./start.sh headless
./start.sh full
docker compose -f docker-compose.dev.yml up
```

`start.sh` clears listeners and uses `DB_PORT=35432`, `BACKEND_PORT=38000`, and `FRONTEND_PORT=35173` by default. Override those variables when the ports are busy.

Backend commands from repo root:

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
uv run --project backend --locked pytest backend/tests -v
```

Frontend commands:

```bash
corepack pnpm@10.30.1 --dir frontend install
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
```

Edge commands:

```bash
npm --prefix edge install
npm --prefix edge test
npm --prefix edge run lint
```

## Production Compose

Create a root `.env` from the template, then start the production stack:

```bash
cp .env.example .env
chmod 600 .env
# edit POSTGRES_PASSWORD, SECRET_KEY, and CHANNEL_CONFIG_ENCRYPTION_KEY
docker compose up -d
```

Docker Compose reads the root `.env` natively, so interactive shells, systemd, and cron backups do not need separate exports. `docker-compose.yml` runs `db`, one-shot `migrate`, `api`, and `worker`. It does not publish the database port and does not run frontend or edge deployments. `EDGE_SYNC_TOKEN` is optional; when unset, `/api/edge-config` returns `404`.

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
| `MQTT_BLOCK_PRIVATE_NETWORKS` | worker | Dispatch-time MQTT private-network guard, default on |
| `MQTT_SOCKET_TIMEOUT_SECONDS` | worker | MQTT socket timeout, default `5.0` |
| `VITE_API_URL` | frontend | Backend base URL baked into the frontend build and used by browser API calls |
| `RELAY_ADMIN_TOKEN` | edge/scripts/GitHub | Protects relay admin endpoints |
| `UPSTREAM_URL` | edge | Cloudflare upstream points to backend; EdgeOne upstream points to Cloudflare |

## Admin Tasks

Run migrations:

```bash
uv run --project backend --locked python -m backend.migrate
```

Reset a password without email:

```bash
docker compose exec api herald-backend reset-password user@example.com
```

For local development with a reachable `DATABASE_URL`:

```bash
uv run --project backend --locked herald-backend reset-password user@example.com
```

Back up PostgreSQL from cron:

```cron
0 3 * * * BACKUP_DIR=/var/backups/herald /path/to/herald/scripts/backup_db.sh
```

`scripts/backup_db.sh` runs `docker compose exec -T db pg_dump -U herald herald` from the repo root, writes `herald-<timestamp>.sql.gz.tmp`, renames it only after gzip succeeds, and deletes `herald-*.sql.gz` files older than `KEEP_DAYS` (default `14`). The root `.env` used for compose startup also covers cron.

Restore from a backup (stop writers first so nothing races the load):

```bash
docker compose stop api worker
gunzip -c backups/herald-<timestamp>.sql.gz | docker compose exec -T db psql -U herald herald
docker compose start api worker
```

Sync edge relay config:

```bash
EDGE_SYNC_TOKEN="$EDGE_SYNC_TOKEN" RELAY_ADMIN_TOKEN="$RELAY_ADMIN_TOKEN" \
  python3 scripts/sync_edge_config.py \
    --backend https://backend.example.com \
    --edges https://cf.example.workers.dev,https://edge.example.cn
```

## Health

- Backend: `GET /health`, returns `503` when the database check fails.
- Frontend static server: `GET /health`
- Cloudflare and EdgeOne relays: `GET /healthz`
