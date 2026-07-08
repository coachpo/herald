# Architecture

## Packages

- `backend/`: FastAPI, PostgreSQL, migrations, auth, ingest, rule evaluation, provider delivery, and edge-config export.
- `frontend/`: React/Vite dashboard that talks directly to the backend through `VITE_API_URL`.
- `edge/`: shared relay protocol modules plus Cloudflare Worker and EdgeOne Pages implementations.

## Runtime Flow

```text
Frontend browser -> Backend /api/*
Direct sender -> Backend /api/ingest/{endpoint_id}
Sender -> Cloudflare relay -> Backend /api/ingest/{endpoint_id}
Sender -> EdgeOne relay -> Cloudflare relay -> Backend /api/ingest/{endpoint_id}
Backend ingest -> messages + deliveries -> worker -> Bark/ntfy/MQTT/Gotify
```

The backend is the only rule engine and provider dispatch engine. Relays only authenticate endpoint keys, validate payload shape, durably buffer envelopes, and forward upstream.

## Backend

- Numbered SQL migrations live in `backend/migrations/` and run through `python -m backend.migrate`.
- Tables are reflected by `backend/database.py`.
- Middleware is pure ASGI. Starlette `CORSMiddleware` is allowed.
- `SECRET_KEY` signs backend token hashes; production rejects default secrets.
- `GET /api/edge-config` exports only `{id, key_sha256}` endpoint digests for relays.

## Ingest

1. Resolve dashed UUID or dashless endpoint id.
2. Authenticate `X-Herald-Ingest-Key` against backend HMAC hash.
3. Parse relay headers after authentication.
4. Insert the message with `ON CONFLICT DO NOTHING`.
5. Evaluate rules and enqueue deliveries only on first insert.
6. Return `201` for new messages and `200` with `duplicate: true` for replayed relay ids.

## Worker

The worker sweeps `sending` deliveries older than 10 minutes back to `retry`, claims due `queued`/`retry` rows with `FOR UPDATE SKIP LOCKED`, and processes each delivery in its own database session. Failed provider sends retry with exponential backoff from `DELIVERY_BACKOFF_BASE_SECONDS` up to `DELIVERY_BACKOFF_MAX_SECONDS`, then become `failed` after `DELIVERY_MAX_ATTEMPTS`. Disabled or missing rules, channels, or messages fail the delivery without retry.

## Edge

Cloudflare uses a Durable Object with SQLite storage and alarms. EdgeOne uses Pages KV with opportunistic drain plus the scheduled GitHub fallback. Both use the same admin endpoints and relay envelope format.
