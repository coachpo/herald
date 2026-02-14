# Operations — Beacon Spear v0.1

## Runtime processes

1) `backend`: Django app (serves JSON APIs + ingest)
2) `frontend`: Next.js app (dashboard UI)
3) `worker`: background delivery worker (polls DB, sends Bark)

## Configuration (env)

Proposed env vars:

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_DEBUG` (false in prod)
- `DATABASE_URL` (Postgres)
- `JWT_SIGNING_KEY` (or reuse `DJANGO_SECRET_KEY`; recommended separate key)
- `JWT_ACCESS_TTL_SECONDS=900`
- `JWT_REFRESH_TTL_SECONDS=2592000` (30 days)
- `JWT_REFRESH_COOKIE_NAME=beacon_refresh`
- `JWT_REFRESH_COOKIE_SECURE=true`
- `JWT_REFRESH_COOKIE_SAMESITE=Strict`

### Next.js

- `NEXT_PUBLIC_BASE_URL` (optional; used for building absolute links in UI)
- `BACKEND_BASE_URL` (optional; only if the frontend server needs to call backend directly)

### Email (SMTP)

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS` (or SSL)
- `DEFAULT_FROM_EMAIL`

### App behavior

- `REQUIRE_VERIFIED_EMAIL_FOR_INGEST=true`
- `MAX_INGEST_BYTES=1048576`
- `DELIVERY_MAX_ATTEMPTS=10`
- `DELIVERY_BACKOFF_BASE_SECONDS=5`
- `DELIVERY_BACKOFF_MAX_SECONDS=1800`
- `BARK_REQUEST_TIMEOUT_SECONDS=5`

### Optional safety

- `BARK_BLOCK_PRIVATE_NETWORKS=true`

## Deploy outline

- Reverse proxy (nginx/caddy) terminates TLS and routes:
  - `/api/*` → Django backend
  - everything else → Next.js frontend
- Postgres for persistence.
- Worker runs as a separate process/service.

## Database maintenance

- Backups: daily logical backups or managed Postgres snapshots.
- Index maintenance: monitor table growth (`messages`, `deliveries`).

## Observability (minimal)

- Structured logs:
  - ingest: endpoint id, message id, payload size
  - deliveries: delivery id, rule id, channel id, status changes
- Basic health endpoints:
  - web: `/healthz`
  - worker: logs + optional “last loop time” metric

## Data deletion

Batch delete can be heavy; recommended approach:

- Implement batch delete as a background job if expected rows are large.
- Provide progress indicator in UI (optional).
