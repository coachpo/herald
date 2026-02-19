# Edge — Beacon Spear Lite

> **v2.0 note:** The edge worker now runs exclusively in Lite mode. The previous proxy/forwarding mode (multi-hop routing, EdgeOne support, env-var-based config) has been removed. All configuration is via Cloudflare KV.

The `edge/` Cloudflare Worker runs Beacon Spear in lite mode: local rule evaluation, template rendering, and HTTP dispatch to Bark/ntfy.

## How It Works

1. Receives `POST /api/ingest/{endpoint_id}` with a JSON body.
2. Authenticates using `token_hash` from KV config.
3. Evaluates forwarding rules locally (field matching, regex, keyword filters).
4. Renders notification templates and dispatches to Bark or ntfy via HTTP.

No backend round-trip required. Best-effort delivery.

## Request Shape

Edge accepts:

- `POST /api/ingest/{endpoint_id}`
  - header: `X-Beacon-Ingest-Key: <ingest_token>`
  - body: JSON payload (validated locally by the worker)
- `GET /healthz`
  - returns `{"ok": true, "mode": "lite"}`

## Configuration

All config is stored in Cloudflare KV (bound as `EDGE_CONFIG`, key `"config"`).

The backend exports config via `GET /api/edge-config`. Push the JSON blob to KV.

Config includes per-endpoint:

- `token_hash` — SHA-256 hex of the ingest token (for auth)
- `rules` — array of forwarding rules with filters, channel config, and payload templates

See `edge/README.md` for the full config shape.

## Supported Providers

- Bark (HTTP API v2)
- ntfy (HTTP publish)
- MQTT: **not supported** (no TCP sockets in Workers)

## Limitations

- Best-effort delivery only. No durable retries or message persistence.
- No message history or audit log at the edge.
- User-supplied regex in rule filters could cause ReDoS.

## Cloudflare Workers Free Tier Compatibility

The lite worker fits within CF Workers free tier limits:

- ~1-3ms CPU per request (well under 10ms limit)
- 1 subrequest per matched rule (well under 50 subrequest limit)
- Config cached in memory after first KV read

## Submodule

Implementation lives in the `edge/` git submodule.
