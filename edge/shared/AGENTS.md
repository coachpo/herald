# edge/shared/AGENTS.md

## Overview

Canonical relay protocol modules imported by Cloudflare Worker code and copied into EdgeOne Pages functions. Edit here first, then rebuild EdgeOne `_shared`.

## Files

| File | Role |
| --- | --- |
| `auth.mjs` | Endpoint id normalization, SHA-256 key digest, constant-time compare |
| `config-cache.mjs` | TTL cache around relay config loading |
| `http.mjs` | JSON response and bearer admin auth helpers |
| `relay.mjs` | Relay headers, envelope shape, forwarding, backoff |
| `validate.mjs` | Public ingest payload validation |

## Protocol Rules

- Endpoint auth compares dashless endpoint ids and `sha256(trim(rawKey))` with backend-exported `key_sha256`.
- Accepted payload fields are `body`, `title`, `group`, `priority`, `tags`, `url`, and `extras`.
- `parseRelayHeaders()` preserves only valid incoming message id / received-at values and sanitizes relay via.
- `forwardEnvelope()` posts to fixed `UPSTREAM_URL` at `/api/ingest/{endpoint_id}` with the original ingest key.
- Permanent upstream statuses are `400, 401, 403, 404, 413, 415, 422`; other failures retry with capped backoff.
- Pending envelopes may include raw ingest keys; dead records in platform runtimes must redact them.

## Generated Copy

```bash
bash edge/edgeone/build.sh
```

`edge/edgeone/edge-functions/_shared/` is generated from this directory. Do not hand-edit or add guidance there. After rebuilding, run the root edge test command.
