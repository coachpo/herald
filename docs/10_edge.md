# Edge Lite

## Current Mode

The `edge/` package is a Cloudflare Worker running Herald lite mode only. It does local validation, local rule evaluation, template rendering, and Bark/ntfy HTTP dispatch from a KV snapshot.

## Routes

- `GET /healthz`
- `POST /api/ingest/{endpoint_id}`

## Ingest Handling

For `POST /api/ingest/{endpoint_id}` the worker:

1. Loads the KV snapshot from `EDGE_CONFIG`, key `config`
2. Finds the ingest endpoint by dashed or dashless UUID
3. Compares `X-Herald-Ingest-Key` directly to the exported `token_hash`
4. Validates the JSON payload and 1 MB size limit
5. Evaluates matching rules
6. Renders templates
7. Dispatches Bark and/or ntfy requests in parallel
8. Returns a `201` response with dispatch results

## KV Snapshot Shape

Backend exports this shape from `GET /api/edge-config`:

- `ingest_endpoints`: `{id, name, token_hash}`
- `channels`: active Bark/ntfy channels with decrypted `config`
- `rules`: enabled rules referencing those channels
- `updated_at`
- `version`

MQTT and Gotify are intentionally excluded from the snapshot.

## Payload Validation

Allowed top-level fields:

- `body` (required)
- `title`
- `group`
- `priority`
- `tags`
- `url`
- `extras`

The worker rejects unknown fields, missing body, invalid types, oversized payloads, and non-JSON content types.

## Supported Providers

- Bark
- ntfy

Not supported in edge-lite:

- MQTT
- Gotify
- durable retries
- stored message history
- backend-style SSRF guardrails

## Important Caveats

- Current auth behavior is not backend-ingest parity: the worker expects the exported `token_hash` value directly.
- Dispatch is best-effort only; failures are reported in the response body, not retried.
- Regex filters can still be expensive; keep them simple.
- `env._liteConfig` caching is in-process only and should not be treated as durable config state.
