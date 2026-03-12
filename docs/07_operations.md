# Operations

## Runtime Processes

- `backend`: Django app serving `/api/*` and `GET /health`
- `worker`: `python manage.py deliveries_worker`
- `frontend`: Vite dev server in development, static files + `GET /health` in the container image
- `edge`: optional Cloudflare Worker lite deployment

## Local Commands

### Whole repo

```bash
./start.sh headless
./start.sh full
```

### Backend

```bash
python manage.py migrate --noinput
python manage.py test
python manage.py runserver 0.0.0.0:8000
python manage.py deliveries_worker
python manage.py smoke_channels --live
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

## Environment Variables

### Backend core

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_DEBUG`
- `DATABASE_URL` (optional parser override)
- `SQLITE_TIMEOUT_SECONDS`
- `JWT_SIGNING_KEY`
- `JWT_ACCESS_TTL_SECONDS`
- `JWT_REFRESH_TTL_SECONDS`
- `TOKEN_HASH_KEY`
- `CHANNEL_CONFIG_ENCRYPTION_KEY`

### Backend app behavior

- `ALLOW_USER_SIGNUP`
- `REQUIRE_VERIFIED_EMAIL_FOR_INGEST`
- `MAX_INGEST_BYTES`
- `DELIVERY_MAX_ATTEMPTS`
- `DELIVERY_BACKOFF_BASE_SECONDS`
- `DELIVERY_BACKOFF_MAX_SECONDS`
- `WORKER_POLL_SECONDS`
- `WORKER_BATCH_SIZE`

### Provider safety/timeouts

- `BARK_REQUEST_TIMEOUT_SECONDS`
- `BARK_BLOCK_PRIVATE_NETWORKS`
- `NTFY_REQUEST_TIMEOUT_SECONDS`
- `NTFY_BLOCK_PRIVATE_NETWORKS`
- `MQTT_SOCKET_TIMEOUT_SECONDS`
- `MQTT_BLOCK_PRIVATE_NETWORKS`

### Frontend / email / CORS

- `VITE_API_URL`
- `APP_BASE_URL`
- `CORS_ALLOWED_ORIGINS`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS`
- `DEFAULT_FROM_EMAIL`

## Storage Notes

- SQLite is the default runtime database in this repo.
- The backend enables WAL mode and timeout tuning to reduce lock errors when API and worker run together.
- `DATABASE_URL` parsing exists, but there is no Postgres client dependency in `backend/requirements.txt`.

## Deployment Notes

- Frontend production build is a static SPA served by `frontend/deploy/server.mjs`.
- Backend and frontend can share an origin, but the shipped architecture also supports direct browser-to-backend calls with CORS.
- Worker should run as a separate long-lived process.
- Edge-lite requires a Cloudflare KV namespace bound as `EDGE_CONFIG`.

## Health Endpoints

- Backend: `GET /health`
- Frontend container: `GET /health`
- Edge-lite: `GET /healthz`

## CI/CD

- `.github/workflows/docker-images.yml` builds arm64 backend/frontend images and publishes to GHCR on push/tag events.
- `.github/workflows/cleanup.yml` prunes old workflow runs and untagged container images.

## Operational Caveats

- Backend refresh and channel creation paths include small retries for transient SQLite lock errors.
- Batch delete is synchronous in the current backend.
- Edge-lite is best-effort only and should not be documented as a durable queue or audit system.
