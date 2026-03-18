# Operations

## Runtime Processes

- `backend`: FastAPI backend serving `/api/*` and `GET /health`.
- `worker`: `python -m backend.worker` (async delivery loop).
- `frontend`: Vite dev server in development, static files + `GET /health` in the container image.
- `edge`: optional Cloudflare Worker lite deployment.

## Local Commands

### Whole repo

```bash
docker compose up          # FastAPI + PostgreSQL + worker
./start.sh --help
./start.sh headless        # helper script: db + backend
./start.sh full            # helper script: db + backend + frontend
```

### Helper script defaults (`start.sh`)

| Port | Default |
|------|---------|
| Database | `35432` |
| Backend | `38000` |
| Frontend | `35173` |

`start.sh full` creates `backend/.venv`, installs backend dependencies there, runs `bootstrap_dev_db.py`, and points the frontend directly at the helper backend with `VITE_API_URL=http://localhost:$BACKEND_PORT`.

### Backend (from repo root)

```bash
python -m pip install -e "backend[test]"
python backend/bootstrap_dev_db.py
python -m pytest backend/tests/ -v
herald-backend
python -m backend.worker
```

The manual/container examples use the package defaults (`5432` / `8000`). They are distinct from the helper script ports above.

### Frontend

```bash
pnpm install
pnpm lint
pnpm build
pnpm dev
pnpm preview
```

Plain `pnpm dev` uses Vite port `3000`. The production static server in `frontend/deploy/server.mjs` listens on `3100`.

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
| `DATABASE_URL` | (required) | PostgreSQL connection string (for example `postgresql://user:pass@host/db`) |
| `DJANGO_SECRET_KEY` | `dev-insecure` | Secret key used for token signing fallback |
| `JWT_SIGNING_KEY` | same as `DJANGO_SECRET_KEY` | JWT signing key |
| `JWT_ACCESS_TTL_SECONDS` | `900` | Access token TTL |
| `JWT_REFRESH_TTL_SECONDS` | `2592000` | Refresh token TTL |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | (empty) | Fernet key for encrypted channel configs |
| `CORS_ALLOWED_ORIGINS` | (empty in code) | Comma-separated allowed origins |
| `ALLOW_USER_SIGNUP` | `true` | Enable/disable signup |
| `DELIVERY_MAX_ATTEMPTS` | `10` | Max delivery retries |
| `DELIVERY_BACKOFF_BASE_SECONDS` | `5` | Retry backoff base |
| `DELIVERY_BACKOFF_MAX_SECONDS` | `1800` | Retry backoff cap |
| `WORKER_POLL_SECONDS` | `1.0` | Worker queue poll interval |
| `WORKER_BATCH_SIZE` | `50` | Max deliveries per poll cycle |
| `DB_POOL_SIZE` | `5` | PostgreSQL pool size |
| `DB_MAX_OVERFLOW` | `10` | Max overflow above pool size |
| `DB_POOL_RECYCLE` | `3600` | Connection recycle time in seconds |
| `DB_POOL_CLASS` | (empty) | Set to `null` to disable pooling |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_FORMAT` | `json` in code | Log output format (`json` or `console`); docker compose overrides to `console` |
| `SENTRY_DSN` | (empty) | Sentry DSN |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Sentry traces sample rate |
| `SENTRY_ENVIRONMENT` | `production` | Sentry environment tag |
| `APP_VERSION` | installed `herald-backend` version, fallback `0.9.0` | Version string in health response |
| `MQTT_BLOCK_PRIVATE_NETWORKS` | `true` | Block private network MQTT targets |
| `MQTT_SOCKET_TIMEOUT_SECONDS` | `5.0` | MQTT socket timeout |

There is no `REQUIRE_VERIFIED_EMAIL_FOR_INGEST` environment variable in the current backend.

## Docker Commands

```bash
docker compose up              # start all (api + db + worker)
docker compose up -d db        # PostgreSQL only
docker compose up api          # API + DB
docker compose logs -f api     # follow API logs
```

`docker-compose.yml` starts PostgreSQL, API, and worker only. It does not launch frontend or edge.

## Health Endpoints

- Backend: `GET /health`
- Frontend container: `GET /health`
- Edge-lite: `GET /healthz`

`GET /health` returns `200` with `status: ok` when the database is connected, or `503` with `status: degraded` when it is not.

## Storage Notes

- PostgreSQL is the only supported runtime database.
- Database access uses SQLAlchemy 2.0 async engine with asyncpg.
- Connection pooling defaults to `QueuePool` with `pool_pre_ping=True` unless `DB_POOL_CLASS=null`.

## Deployment Notes

- Frontend production build is a static SPA served by `frontend/deploy/server.mjs` on port `3100`.
- Backend and frontend can share an origin, but direct browser-to-backend with CORS is supported.
- Worker should run as a separate long-lived process.
- Edge-lite requires a Cloudflare KV namespace bound as `EDGE_CONFIG`.

## CI/CD

- `.github/workflows/docker-images.yml` builds arm64 backend/frontend images and publishes to GHCR on push/tag events.
- `.github/workflows/cleanup.yml` prunes old workflow runs and untagged container images.
- Root CI does not build or deploy `edge/`.

## Operational Caveats

- Backend refresh and several write paths can return `503 temporarily_unavailable` during transient database contention.
- Batch delete is synchronous in the current backend.
- Verification and password-reset request routes do not send mail in this repo; they only create hashed tokens and log the event.
- Edge-lite is best-effort only and should not be documented as a durable queue or audit system.
