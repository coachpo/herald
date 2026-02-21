# Operations — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

## Runtime processes

1. `backend`: Django app (serves JSON APIs + ingest)
2. `frontend`: React 19 + TypeScript SPA (Vite build, React Router dashboard UI)
3. `worker`: background delivery worker (polls DB, sends Bark/ntfy/MQTT)

Frontend UI stack:

- Tailwind CSS v4 via `@tailwindcss/vite`
- shadcn/ui ecosystem (Radix primitives, CVA, `clsx`, `tailwind-merge`)
- `react-hook-form` + `zod` for form handling and validation

## Configuration (env)

Proposed env vars:

### Django

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_DEBUG` (false in prod)
- `JWT_SIGNING_KEY` (or reuse `DJANGO_SECRET_KEY`; recommended separate key)
- `JWT_ACCESS_TTL_SECONDS=900`
- `JWT_REFRESH_TTL_SECONDS=2592000` (30 days)

### Frontend (Vite)

- `VITE_API_URL` (build-time; browser-facing API base URL used by the frontend app)

### Backend app URL

- `APP_BASE_URL` (used by backend for verification/reset email links)

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
- `NTFY_REQUEST_TIMEOUT_SECONDS=5`
- `MQTT_SOCKET_TIMEOUT_SECONDS=5`

### Optional safety

- `BARK_BLOCK_PRIVATE_NETWORKS=true`
- `NTFY_BLOCK_PRIVATE_NETWORKS=true`
- `MQTT_BLOCK_PRIVATE_NETWORKS=true`

## Deploy outline

- Reverse proxy (nginx/caddy) terminates TLS and routes:
  - `/api/*` → Django backend
  - everything else → frontend SPA (Vite build, typically served by nginx)
- Postgres for persistence.
- Worker runs as a separate process/service.

## Optional edge forwarders

If you deploy edge functions (Cloudflare Workers / Tencent EdgeOne) in front of ingest,
they should forward `POST /api/ingest/{endpoint_id}` to the backend (or to another edge hop).

See `docs/10_edge.md`.

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
