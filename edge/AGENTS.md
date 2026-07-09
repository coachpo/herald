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

## Command Notes

- Root `AGENTS.md` carries the normal edge test/lint commands.
- Extra package commands are `npm --prefix edge install`, `npm --prefix edge run dev`, and `npm --prefix edge run deploy`.
- For EdgeOne, run `bash edge/edgeone/build.sh` before local dev or deployment so shared modules are copied into the Pages function tree.

## HTTP Surface

- `GET /healthz`
- `POST /api/ingest/{endpoint_id}`
- `POST /admin/config`
- `GET /admin/status`
- `POST /relay/drain`

Admin routes require `Authorization: Bearer $RELAY_ADMIN_TOKEN`.

## Runtime Notes

- `edge/shared/` is canonical; `edge/edgeone/edge-functions/_shared/` is generated and must not be hand-edited.
- Cloudflare uses Durable Object SQLite and alarms.
- EdgeOne uses Pages KV with `p_` pending keys and `d_` dead keys.
- EdgeOne KV binding is global `EDGE_CONFIG`, not `context.env.EDGE_CONFIG`.
- `UPSTREAM_URL` is fixed deployment config, not user input.
- Relays preserve valid incoming message id / received-at headers and append their platform to relay via.
- Relays store raw ingest keys only inside pending envelopes and redact them in dead records.
