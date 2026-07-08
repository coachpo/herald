# edge/AGENTS.md

## Overview

Store-and-forward relay package for Cloudflare Workers and EdgeOne Pages. The edge code authenticates endpoint keys with `key_sha256`, validates payload shape, buffers envelopes, and forwards upstream. Backend remains the delivery engine.

## Structure

```text
edge/
├── shared/       # auth, validation, relay, config-cache, HTTP helpers
├── cloudflare/   # Worker entry, Durable Object, wrangler config
├── edgeone/      # Pages function and build helper
└── tests/        # node:test suite
```

## Commands

```bash
npm install
npm test
npm run lint
npm run dev
npm run deploy
```

For EdgeOne, run `bash edgeone/build.sh` before local dev or deployment so shared modules are copied into the Pages function tree.

## HTTP Surface

- `GET /healthz`
- `POST /api/ingest/{endpoint_id}`
- `POST /admin/config`
- `GET /admin/status`
- `POST /relay/drain`

Admin routes require `Authorization: Bearer $RELAY_ADMIN_TOKEN`.

## Runtime Notes

- Cloudflare uses Durable Object SQLite and alarms.
- EdgeOne uses Pages KV with `p_` pending keys and `d_` dead keys.
- EdgeOne KV binding is global `EDGE_CONFIG`, not `context.env.EDGE_CONFIG`.
- `UPSTREAM_URL` is fixed deployment config, not user input.
- Relays store raw ingest keys only inside pending envelopes and redact them in dead records.
