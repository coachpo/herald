# Edge Lite Tradeoffs

This file records what edge-lite now covers well and what still belongs to the full backend/worker architecture.

## What Edge Lite Solves Today

- Low-latency ingest handling from Cloudflare Workers
- Local rule matching on the exported snapshot
- Local template rendering
- Bark and ntfy HTTP dispatch without calling the backend at request time

## What Still Belongs To The Backend

- Durable message storage
- Delivery retries and backoff
- MQTT publishing
- Auditable delivery history
- Backend SSRF protections on provider destinations

## Practical Consequences

- Edge-lite is best-effort fanout, not a replacement for the backend worker
- Backend remains the only implementation with persisted `Message` and `Delivery` rows
- Documentation should present edge-lite as a narrower deployment mode, not a feature-equivalent runtime

## Current Sharp Edges

- Auth uses the exported `token_hash` string directly
- Provider dispatch is HTTP-only
- Failures are returned in the immediate response and then discarded
- Regex filters remain user-controlled and can still be computationally expensive

## When To Use Edge Lite

Use it when you want:

- Cloudflare-hosted best-effort HTTP fanout
- No MQTT dependency
- Lower latency and fewer moving parts than the full backend/worker path

Do not present it as the default answer when durable retries or stored history matter.
