# edge/AGENTS.md

## Overview

Herald Lite for Cloudflare Workers. Reads config from KV, evaluates rules locally, renders templates, and dispatches to Bark/ntfy over HTTP. No backend round-trip, no durable queue.

## Commands

```bash
npm install
npm test
npm run lint
npm run dev
npm run deploy
```

## Architecture

```text
edge/
├── wrangler.toml             # Worker entry + EDGE_CONFIG binding
└── src/
    ├── cloudflare-worker.mjs # Worker entry point configured in Wrangler
    ├── lite.mjs              # request handler, auth, validation, dispatch orchestration
    ├── rules.mjs             # rule filter evaluation
    ├── template.mjs          # Mustache-style rendering + context
    ├── providers.mjs         # Bark and ntfy HTTP builders/dispatch
    └── lite.test.mjs         # Node test suite
```

## Request Flow

```text
GET /healthz -> {"ok": true, "mode": "lite"}
POST /api/ingest/{endpoint_id}
  -> load KV config
  -> match dashed UUID or dashless hex endpoint ids
  -> compare X-Herald-Ingest-Key to endpoint.token_hash
  -> validate JSON payload
  -> match rules
  -> render templates
  -> dispatch Bark/ntfy in parallel
  -> return {message_id, matched_rules, dispatched, results}
```

## Config Shape

- KV binding: `EDGE_CONFIG`
- KV key: `config`
- Snapshot payload contains `ingest_endpoints`, `channels`, `rules`, `updated_at`, and `version`.
- Only Bark and ntfy channels are exported from backend edge-config; MQTT and Gotify are excluded.

## Conventions

- Pure ESM package with no runtime dependencies.
- `wrangler.toml` points at `src/cloudflare-worker.mjs`, binds `EDGE_CONFIG`, and currently pins `compatibility_date = "2026-02-16"`.
- Linting is `node --check`; tests use Node's built-in test runner and currently cover rules, templates, providers, and integration flows.
- Ingest endpoint lookup accepts both dashed UUIDs and dashless hex IDs.
- Payload validation mirrors backend's allowed top-level keys, requires `body`, and enforces a 1 MB body limit.
- Matching rules dispatch concurrently via `Promise.allSettled()`.
- Template context keys are `message`, `request`, and `ingest_endpoint`.
- Root CI does not build or deploy `edge/`; run `npm run deploy` explicitly when this package changes.

## Limitations And Caveats

- HTTP providers only: Bark and ntfy.
- Best-effort only: no persistence, no retry queue, no delivery history.
- Current auth behavior compares the raw `X-Herald-Ingest-Key` header directly against exported `token_hash` values from KV config.
- `dispatched` in the ingest response reflects attempted dispatch results, not every matched rule.
- Edge providers do not implement backend-style SSRF checks.
- `env._liteConfig` caching is in-process only; do not treat it as durable state.
- User-supplied regex can still be expensive; keep patterns simple.
