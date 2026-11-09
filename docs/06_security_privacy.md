# Security And Privacy

## Auth

- Dashboard APIs use bearer access tokens.
- Passwords use salted PBKDF2-SHA256 hashes. Access tokens are signed HS256 JWTs; refresh tokens are stored as HMAC hashes, rotated on use, and reuse of a revoked token revokes its whole family.
- Browser requests use `credentials: "omit"`.
- The frontend keeps refresh tokens in `sessionStorage` and access tokens in memory.
- Logout revokes the submitted refresh token; the change-password API revokes all of that user's refresh tokens. Already issued access tokens are not individually revoked and remain cryptographically valid until expiry. The operator password-reset CLI only replaces the password hash; it does not revoke sessions.

## Keys

| Secret | Stored In | Purpose |
| --- | --- | --- |
| Raw ingest key | Sender and relay buffer until forwarded | Endpoint authentication |
| `token_hash` | Backend DB | Backend HMAC check |
| `key_sha256` | Backend DB and relay config | Relay offline key check |
| `SECRET_KEY` | Backend env | HMAC secret and JWT fallback secret |
| `JWT_SIGNING_KEY` | Backend env | Optional access-token signing override |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | Backend env | Fernet channel config encryption; required in production |
| `EDGE_SYNC_TOKEN` | Backend env and sync script | Pull relay config |
| `RELAY_ADMIN_TOKEN` | Relay env, sync script; GitHub Actions secret when the manual drain workflow is used | Relay admin endpoints |

`APP_ENV=production` rejects default backend secrets and an absent channel encryption key. In development, encryption can derive a key from `SECRET_KEY` when no explicit key is configured. Preserve the encryption key when restoring channel data; changing it does not re-encrypt existing rows. See [environment settings](07_operations.md#environment).

## Ingest Safety

- Only JSON is accepted.
- Payloads above 1 MiB are rejected.
- Unknown top-level keys are rejected.
- Sensitive request headers are redacted before persistence.
- Relay config never contains channel credentials.

Redaction covers the names recognized by [core/redaction.py](../backend/core/redaction.py), not arbitrary payload content, query parameters, or upstream response bodies. Message data and provider metadata can contain sensitive content supplied by senders/providers; no general-purpose secret scrubber or retention guarantee is implied. For deletion semantics, see [Data Model](03_data_model.md#deletion-and-relationships).

The API's current rate limits are process-local, not a global cross-worker quota; settings and proxy prerequisites are documented in [Operations](07_operations.md#environment).

## Outbound Safety

Backend providers use [SSRF checks](../backend/core/ssrf.py) before dispatch. Bark, ntfy, and Gotify validate destination URLs at channel creation and dispatch. MQTT channel creation always blocks private, loopback, and link-local broker hosts; `MQTT_BLOCK_PRIVATE_NETWORKS` only affects the dispatch-time MQTT private-network check. Do not disable these accepted outbound-safety constraints as a convenience for local/private providers.

Relays only fetch fixed upstream URLs. They do not fetch user-controlled provider URLs.

## Operational Hygiene

- Do not commit `.env` files or copied keys.
- Do not log raw auth headers, ingest keys, passwords, refresh tokens, or decrypted channel configs.
- Do not move frontend auth tokens into `localStorage`.

## Relay Threat Model Notes

1. Buffered raw ingest keys: relays must replay the original key to the next hop. Keys exist in pending buffers (Cloudflare Durable Object SQLite / EdgeOne KV), runtime memory, and forwarding requests; successful forwarding deletes the pending record. Dead records redact `ingest_key` as `"[redacted]"`. Keep buffers draining normally and restrict KV/DO read access to the same trust level as `RELAY_ADMIN_TOKEN`. Deployment operators must verify TLS, platform storage protection, and access controls; repository code does not establish the state of a live deployment.
2. Global primary-key idempotency oracle: an authenticated sender can learn `duplicate:true` if a supplied UUID exists for any user; collisions also suppress that sender's insert and delivery creation. The current schema uses a global key rather than per-tenant idempotency. Automatically minted ids are random UUIDv4, but callers may supply any valid UUID; randomness is not enforced on input. Authentication still precedes the duplicate check, the message owner comes from the authenticated endpoint, and the duplicate response does not disclose another message's contents. Deployments requiring tenant-scoped idempotency need a separate design change.
3. Single delivery-worker constraint: claiming uses `FOR UPDATE SKIP LOCKED`, but stale recovery requeues any `sending` row older than 10 minutes without claim ownership or heartbeat, and each claimed batch is dispatched serially. Multiple active workers can reclaim a batch another worker is still processing. The supplied production compose declares one `worker` service; do not scale it horizontally until claim ownership and stale recovery have a concurrency-safe design and validation. Even one worker does not guarantee exactly-once provider effects: a successful send followed by failure to record success may be retried.
