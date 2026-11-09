# edge/shared/AGENTS.md

## Shared Protocol Constraints

- This is the canonical source imported by Cloudflare and copied into EdgeOne; do not add guidance or edit modules in the generated `edgeone/edge-functions/_shared/` copy.
- `auth.mjs` compares dashless endpoint IDs and `sha256(trim(rawKey))` against exported `key_sha256`; keep the backend export and relay verifier compatible.
- `validate.mjs` accepts `body`, `title`, `group`, `priority`, `tags`, `url`, and `extras`. Check backend ingest validation alongside relay validation when changing the public payload.
- `relay.mjs` preserves only valid message-id/received-at values and sanitizes relay-via; `forwardEnvelope()` posts to fixed `UPSTREAM_URL/api/ingest/{endpoint_id}` with the original ingest key.
- Permanent upstream statuses are `400, 401, 403, 404, 413, 415, 422`; other failures retry with capped backoff. Pending envelopes may contain raw keys; platform dead-record paths must redact them.
- After changes, run the parent edge test/lint commands. The test pre-hook rebuilds the EdgeOne copy; explicit rebuild is `bash edge/edgeone/build.sh`.
