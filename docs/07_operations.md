# Operations

## Runtime Processes

- `backend`: FastAPI backend serving `/api/*` and `GET /health`
- `worker`: `python -m backend.worker` (async delivery loop)
- `frontend`: Vite dev server in development, static files + `GET /health` in the container image
- `edge`: optional Cloudflare Worker lite deployment

## Local Commands

### Whole repo

```bash
docker compose up          # FastAPI + PostgreSQL + worker
./start.sh headless        # backend only
./start.sh full            # backend + frontend
```

### Backend (from repo root)

```bash
python -m pip install -r backend/requirements.txt
python -m pytest backend/tests/ -v
uvicorn backend.main:app --host 0.0.0.0 --port 8001
python -m backend.worker
```

### Frontend

```bash
pnpm install
pnpm lint
pnpm build
pnpm dev
```

### Edge

```bash
npm install
npm test
npm run lint
npm run dev
npm run deploy
```

## Backend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | (required) | PostgreSQL connection string (e.g. postgresql://user:pass@host/db) |
| DJANGO_SECRET_KEY | dev-insecure | Secret key used for token signing fallback |
| JWT_SIGNING_KEY | (same as `DJANGO_SECRET_KEY`) | JWT signing key |
| JWT_ACCESS_TTL_SECONDS | 900 | Access token TTL |
| JWT_REFRESH_TTL_SECONDS | 2592000 | Refresh token TTL |
| TOKEN_HASH_KEY | (empty) | Optional hash key for token hashing |
| CHANNEL_CONFIG_ENCRYPTION_KEY | (empty) | Fernet key for encrypted channel configs |
| CORS_ALLOWED_ORIGINS | (empty) | Comma-separated allowed origins |
| ALLOW_USER_SIGNUP | true | Enable/disable signup |
| DELIVERY_MAX_ATTEMPTS | 10 | Max delivery retries |
| DELIVERY_BACKOFF_BASE_SECONDS | 5 | Retry backoff base |
| DELIVERY_BACKOFF_MAX_SECONDS | 1800 | Retry backoff cap |
| WORKER_POLL_SECONDS | 1.0 | Worker queue poll interval |
| WORKER_BATCH_SIZE | 50 | Max deliveries per poll cycle |
| DB_POOL_SIZE | 5 | PostgreSQL pool size |
| DB_MAX_OVERFLOW | 10 | Max overflow above pool size |
| DB_POOL_RECYCLE | 3600 | Connection recycle time in seconds |
| DB_POOL_CLASS | (empty) | Set to `null` to disable pooling |
| LOG_LEVEL | INFO | Logging level |
| LOG_FORMAT | json | Log output format (`json` or `console`) |
| SENTRY_DSN | (empty) | Sentry DSN |
| SENTRY_TRACES_SAMPLE_RATE | 0.1 | Sentry traces sample rate |
| SENTRY_ENVIRONMENT | production | Sentry environment tag |
| APP_VERSION | (from `backend/VERSION`) | Version string in health response |
| MQTT_BLOCK_PRIVATE_NETWORKS | true | Block private network MQTT targets |
| MQTT_SOCKET_TIMEOUT_SECONDS | 5.0 | MQTT socket timeout |

## Docker Commands

```bash
docker compose up              # start all (API + DB + worker)
docker compose up -d db        # PostgreSQL only
docker compose logs -f api     # follow API logs
```

## Health Endpoints

- Backend: `GET /health`
- Frontend container: `GET /health`
- Edge-lite: `GET /healthz`

## Storage Notes

- PostgreSQL is the only supported runtime database.
- Database access uses SQLAlchemy 2.0 async engine with asyncpg.
- Connection pooling defaults to `QueuePool` with `pool_pre_ping=True`.

## Deployment Notes

- Frontend production build is a static SPA served by `frontend/deploy/server.mjs`.
- Backend and frontend can share an origin, but direct browser-to-backend with CORS is supported.
- Worker should run as a separate long-lived process.
- Edge-lite requires a Cloudflare KV namespace bound as `EDGE_CONFIG`.

## CI/CD

- `.github/workflows/docker-images.yml` builds arm64 backend/frontend images and publishes to GHCR on push/tag events.
- `.github/workflows/cleanup.yml` prunes old workflow runs and untagged container images.

## Operational Caveats

- Backend refresh and channel creation paths include retries for transient database errors.
- Batch delete is synchronous in the current backend.
- Edge-lite is best-effort only and should not be documented as a durable queue or audit system.
