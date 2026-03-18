# Architecture

## High-Level Packages

### Backend (`backend/`)

- FastAPI + SQLAlchemy 2.0 + asyncpg (async PostgreSQL).
- Owns auth, ingest, message storage, channel/rule CRUD, and edge-config export.
- Runs an async delivery worker for Bark, ntfy, MQTT, and Gotify.
- Uses pure ASGI middleware for CORS, request IDs, and access logging.
- Exposes `GET /health`, which returns `200` when the database is reachable and `503` with `status: degraded` when it is not.

### Frontend (`frontend/`)

- React 19 + Vite + React Router SPA.
- Talks directly to backend APIs using `VITE_API_URL`.
- Stores refresh token in `sessionStorage` and access token in memory.

### Edge (`edge/`)

- Cloudflare Worker lite mode.
- Reads config snapshot from KV.
- Evaluates rules locally and dispatches Bark/ntfy HTTP requests.
- Does not persist messages or retry failures.

## Runtime Communication

```text
Browser -> Backend /api/* via VITE_API_URL
Ingest -> Backend Message row + Delivery rows
Worker -> Bark / ntfy / MQTT / Gotify
Backend /api/edge-config -> KV snapshot -> Edge lite
Edge lite -> Bark / ntfy HTTP only
```

## Backend Request Model

### Authenticated dashboard APIs

- Access token sent as `Authorization: Bearer <token>`.
- Refresh token sent in JSON body to `/api/auth/refresh`.
- Backend does not rely on session cookies for API auth.
- Read routes work for authenticated users.
- The shipped frontend disables common mutating dashboard flows for unverified users, but the current backend does not universally enforce verified-email gating on every dashboard write route.

### Ingest API

- Public path: `POST /api/ingest/{endpoint_id}`.
- Supports both dashed UUID and dashless hex IDs.
- Requires `X-Herald-Ingest-Key`.
- Requires `Content-Type: application/json`.
- Requires an active user with non-null `email_verified_at`; there is no config toggle for this in the current backend.

## Ingest And Delivery Flow

1. Backend finds the ingest endpoint by path ID.
2. Backend hashes the ingest key and validates it with a constant-time comparison.
3. Backend validates payload shape, content type, and size.
4. Backend stores a `Message` row with structured fields and redacted request metadata.
5. Backend evaluates enabled `ForwardingRule` rows for the user.
6. Backend creates `Delivery` rows for matches.
7. Worker polls due deliveries and dispatches them.
8. Worker writes success/failure metadata back to the delivery rows.

## Storage Model

- PostgreSQL is the production database, accessed via SQLAlchemy 2.0 async engine with asyncpg.
- The FastAPI backend requires PostgreSQL; SQLite is not supported. `DATABASE_URL` configures the connection.
- Delivery queue state lives in the database, not in an external queue system.
- Channel configs are encrypted at rest and decrypted only at dispatch or edge-export boundaries.

## Worker Model

- Typically launched as `uv run --project backend --locked python -m backend.worker`.
- Async event loop polls `queued` and `retry` rows.
- Uses `SELECT ... FOR UPDATE SKIP LOCKED` to avoid duplicate processing.
- Retries with exponential backoff until `DELIVERY_MAX_ATTEMPTS`.
- Dispatches to Bark, ntfy, MQTT, and Gotify providers.
- Bark, ntfy, and Gotify use default private-network SSRF blocking; MQTT additionally exposes `MQTT_BLOCK_PRIVATE_NETWORKS`.

## Frontend Architecture Notes

- Production architecture is direct browser-to-backend communication; same-origin hosting is optional, not required.
- Plain `pnpm dev` runs Vite on port `3000` with a proxy aimed at `http://localhost:8000`.
- `start.sh full` instead runs the frontend on `35173` by default and points it directly at the helper backend port (`38000`).
- Auth-gated routes live under `DashboardLayout`; public flows live under `AuthLayout`.

## Auth Token Request Notes

- Verification and password-reset request endpoints create hashed tokens in PostgreSQL and log the event.
- The current repo does not include outbound email delivery for those flows.

## Edge Lite Notes

- Cloudflare-only runtime in the current repo; do not document EdgeOne or proxy mode as active features.
- `GET /api/edge-config` exports only active ingest endpoints plus Bark/ntfy channels and rules.
- Current lite auth compares the raw `X-Herald-Ingest-Key` header directly against exported `token_hash` values from KV.

## Health Endpoints

- Backend API/process health: `GET /health`
- Frontend container health: `GET /health`
- Edge-lite health: `GET /healthz`
