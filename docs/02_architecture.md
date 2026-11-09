# Architecture

## Packages

- `backend/`: FastAPI, PostgreSQL, migrations, auth, ingest, rule evaluation, provider delivery, and edge-config export.
- `frontend/`: React/Vite dashboard. Browser requests use the backend origin configured by `VITE_API_URL`, or the page origin when unset; the Vite development server can proxy same-origin API requests.
- `edge/`: shared relay protocol modules plus Cloudflare Worker and EdgeOne Pages implementations.

## Runtime Flow

```text
Frontend browser -> Backend /api/*
Direct sender -> Backend /api/ingest/{endpoint_id}
Sender -> Cloudflare relay -> Backend /api/ingest/{endpoint_id}
Sender -> EdgeOne relay -> Cloudflare relay -> Backend /api/ingest/{endpoint_id}
Backend ingest -> messages + deliveries -> worker -> Bark/ntfy/MQTT/Gotify
```

The backend is the only rule engine and provider dispatch engine. Relays only authenticate endpoint keys, validate payload shape, buffer envelopes, and forward upstream. These are supported paths, not a statement about deployed infrastructure: each relay's fixed `UPSTREAM_URL` selects its next hop, so EdgeOne may also forward directly to the backend. Queue persistence and retry limitations are described in [Edge Relays](10_edge.md).

Both root Compose files run separate `db`, `migrate`, `api`, and `worker` services, not the frontend or edge runtimes. The local `start.sh` helper starts the database and API, optionally Vite, but **not the delivery worker**. Operators must start a worker for queued deliveries to leave the backend; see [Operations](07_operations.md) for the appropriate startup path.

## Backend

- Numbered SQL migrations live in `backend/migrations/` and run through `python -m backend.migrate`.
- Tables are reflected by `backend/database.py`.
- Middleware is pure ASGI. Starlette `CORSMiddleware` is allowed.
- `SECRET_KEY` HMAC-hashes ingest keys and refresh tokens; JWT signing uses `JWT_SIGNING_KEY`, falling back to `SECRET_KEY`. Production rejects default secrets. Key handling and other security obligations are owned by [Security and Privacy](06_security_privacy.md).
- `GET /api/edge-config` exports a versioned relay config: a 16-hex-character `version`, an ISO `updated_at`, and active non-revoked/non-deleted endpoint `{id, key_sha256}` digests.

## Ingest

1. Resolve dashed UUID or dashless endpoint id.
2. Authenticate `X-Herald-Ingest-Key` against backend HMAC hash.
3. Parse relay headers after authentication.
4. Validate JSON content type, byte size, encoding, and payload fields.
5. Insert the message with `ON CONFLICT DO NOTHING` on the message id.
6. Evaluate enabled rules and enqueue matching deliveries in the same transaction, only on first insert. Current endpoint/tag matching limitations are documented in the [API Guide](04_api_spec.md#rules).
7. Return `201` for new messages and `200` with `duplicate: true` for replayed message ids. Requests without an id receive a new UUID; body content alone is not a deduplication key.

## Worker

The worker sweeps `sending` deliveries older than 10 minutes back to `retry`, claims due `queued`/`retry` rows with `FOR UPDATE SKIP LOCKED`, and processes a claimed batch serially, with one database session per delivery. Failed provider sends retry with exponential backoff from `DELIVERY_BACKOFF_BASE_SECONDS` up to `DELIVERY_BACKOFF_MAX_SECONDS`, then become `failed` after `DELIVERY_MAX_ATTEMPTS`. Disabled/missing rules or channels, and missing messages, fail the delivery without retry.

Claiming and provider sends are separate transactions. A send can succeed before its result is persisted, so recovery or retries may send again; relay message-id deduplication does not provide provider-level exactly-once delivery. The worker reads the current rule template and channel configuration when it sends, rather than an enqueue-time snapshot.

## Edge

Cloudflare uses a Durable Object with SQLite storage and alarms. EdgeOne uses Pages KV with opportunistic drain; the repository's GitHub drain workflow currently supports manual dispatch only (its schedule is commented out), so it does not guarantee retries during idle periods. Both use the same admin endpoints and relay envelope format.

Configuration flows separately from messages: an operator runs `scripts/sync_edge_config.py` to fetch the backend's authenticated `/api/edge-config` export and post it to each relay's `/admin/config`. Endpoint changes are not automatically pushed; see [Edge Relays](10_edge.md) for synchronization and drain procedures.
