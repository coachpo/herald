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

`start.sh` uses helper ports `35432` for PostgreSQL, `38000` for the backend, and `35173` for Vite unless overridden.

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

Set required secrets before `docker compose up -d`:

```bash
export POSTGRES_PASSWORD='<database password>'
export SECRET_KEY='<random backend secret>'
export CHANNEL_CONFIG_ENCRYPTION_KEY='<fernet key>'
export EDGE_SYNC_TOKEN='<random sync token>'
docker compose up -d
```

`docker-compose.yml` runs `db`, one-shot `migrate`, `api`, and `worker`. It does not publish the database port and does not run frontend or edge deployments.

Generate a Fernet key:

```bash
uv run --project backend --locked python - <<'PY'
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
```

## Environment

| Variable | Scope | Notes |
| --- | --- | --- |
| `DATABASE_URL` | backend | PostgreSQL URL |
| `APP_ENV` | backend | `development` or `production` |
| `SECRET_KEY` | backend | HMAC and JWT fallback key; production rejects the default |
| `JWT_SIGNING_KEY` | backend | Optional JWT signing override |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | backend | Required in production |
| `EDGE_SYNC_TOKEN` | backend/scripts | Machine token for `GET /api/edge-config` |
| `CORS_ALLOWED_ORIGINS` | backend | Comma-separated browser origins |
| `FORWARDED_ALLOW_IPS` | backend | Trusted proxy IPs for uvicorn forwarded headers |
| `RATE_LIMIT_INGEST_PER_MINUTE` | backend | Ingest token bucket limit |
| `RATE_LIMIT_AUTH_PER_MINUTE` | backend | Auth token bucket limit |
| `ALLOW_USER_SIGNUP` | backend | Disable after initial user creation if desired |
| `SENTRY_DSN` | backend/worker | Enables Sentry for API and worker |
| `RELAY_ADMIN_TOKEN` | edge/scripts/GitHub | Protects relay admin endpoints |
| `UPSTREAM_URL` | edge | Cloudflare upstream points to backend; EdgeOne upstream points to Cloudflare |

## Admin Tasks

Run migrations:

```bash
uv run --project backend --locked python -m backend.migrate
```

Reset a password without email:

```bash
uv run --project backend --locked herald-backend reset-password user@example.com
```

Back up PostgreSQL from cron:

```cron
0 3 * * * BACKUP_DIR=/var/backups/herald /path/to/herald/scripts/backup_db.sh
```

Sync edge relay config:

```bash
python3 scripts/sync_edge_config.py --help
```

## Health

- Backend: `GET /health`
- Frontend static server: `GET /health`
- Cloudflare and EdgeOne relays: `GET /healthz`
