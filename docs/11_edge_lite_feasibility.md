# Edge "Beacon Spear Lite" Feasibility Assessment

Date: 2026-02-19

## Context

Goal: evaluate whether `edge/` can become a headless "beacon-spear lite" Cloudflare Worker by consuming exported configuration from the main application.

Reviewed sources:

- `docs/01_prd.md`
- `docs/02_architecture.md`
- `docs/03_data_model.md`
- `docs/04_api_spec.md`
- `docs/10_edge.md`
- `docs/openapi.yaml`
- `edge/src/core.mjs`
- `edge/src/env.mjs`
- `edge/wrangler.toml`

## Q1 — Can the app export configs in a format that `edge/` can consume?

## Current state

- There is **no existing config export API** and no defined export schema for edge runtime consumption.
- Current edge config is environment-variable based and only supports proxy forwarding concerns:
  - incoming key validation
  - endpoint pinning
  - upstream URL + key
  - hop loop guard

## Feasibility

- **Yes, feasible to add.**
- Existing backend data model already contains needed entities:
  - ingest endpoints
  - channels (bark/ntfy/mqtt)
  - forwarding rules + payload templates

## Suggested export shape (high-level)

A per-user edge config payload would include:

- `ingest_endpoints`: endpoint ids + auth material usable by edge
- `channels`: channel type + decrypted runtime config
- `rules`: filters + target channel + payload template
- optional metadata: config version, checksum, updated_at

## Q2 — Can `edge/` run purely headless using only that config?

## Current `edge/` behavior

`edge/src/core.mjs` is a stateless ingest forwarder:

- accepts `POST /api/ingest/{endpoint_id}`
- validates incoming key(s)
- appends/forwards query params
- rewrites `X-Beacon-Ingest-Key` for upstream hop
- forwards body as-is
- does **not** validate message payload
- does **not** evaluate rules
- does **not** render templates
- does **not** send provider notifications itself

## Headless-lite viability

- **Yes, partially.**
- It can become a headless relay for HTTP providers if edge adds:
  - local payload validation
  - rule filter evaluation
  - template rendering
  - provider dispatch via `fetch()`

## Capability matrix

- Bark delivery (HTTP): feasible
- ntfy delivery (HTTP): feasible
- MQTT delivery: **not feasible in Workers** (no raw TCP sockets)

## Operational implications

A truly headless-lite worker would likely be:

- fire-and-forget by default
- limited/no durable retry semantics unless extra Cloudflare state services are added
- limited/no message history unless D1/KV/DO persistence is introduced

## Q3 — Would this work within Cloudflare Worker constraints?

## Constraints impact

- Runtime CPU/memory limits: acceptable for filter+template+HTTP dispatch at moderate scale
- Subrequest quotas: depends on number of matching rules/channels per ingest event
- No TCP sockets: blocks native MQTT publishing
- Stateless execution model: durable queue/retry requires KV, Durable Objects, and/or Queues

## Conclusion

- **Yes**, a Cloudflare Worker "beacon-spear lite" is viable for **HTTP-based forwarding** (Bark + ntfy), with config exported from backend and consumed at edge.
- **No**, it is not functionally equivalent to the full backend+worker architecture without additional infrastructure.
- Without extra state services, this should be framed as:
  - stateless ingest + rules + template + HTTP fanout
  - best-effort delivery
  - no durable retry/history guarantees

## Recommended architecture direction

1. Add backend export pipeline for edge config (versioned JSON).
2. Distribute config to Cloudflare KV (push on config changes).
3. Extend `edge/` runtime with local rule evaluation + template rendering.
4. Keep MQTT out of lite scope (or route MQTT via backend).
5. Decide explicitly whether lite supports:
   - durable retries
   - message audit/history
   and provision D1/DO/Queues only if required.

## Scope positioning

Call this mode:

- **"Beacon Spear Lite (Edge)"** = low-latency, HTTP-channel, best-effort forwarding
- **Full Beacon Spear** = persistent storage, durable retries, full provider support including MQTT
