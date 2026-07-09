# Security And Privacy

## Auth

- Dashboard APIs use bearer access tokens.
- Refresh tokens are stored as hashes and rotated on use.
- Browser requests use `credentials: "omit"`.
- The frontend keeps refresh tokens in `sessionStorage` and access tokens in memory.

## Keys

| Secret | Stored In | Purpose |
| --- | --- | --- |
| Raw ingest key | Sender and relay buffer until forwarded | Endpoint authentication |
| `token_hash` | Backend DB | Backend HMAC check |
| `key_sha256` | Backend DB and relay config | Relay offline key check |
| `SECRET_KEY` | Backend env | HMAC secret and JWT fallback secret |
| `JWT_SIGNING_KEY` | Backend env | Optional access-token signing override |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | Backend env | Channel config encryption |
| `EDGE_SYNC_TOKEN` | Backend env and sync script | Pull relay config |
| `RELAY_ADMIN_TOKEN` | Relay env, sync script, GitHub secret | Relay admin endpoints |

## Ingest Safety

- Only JSON is accepted.
- Payloads above 1 MiB are rejected.
- Unknown top-level keys are rejected.
- Sensitive request headers are redacted before persistence.
- Relay config never contains channel credentials.

## Outbound Safety

Backend providers use SSRF checks before HTTP dispatch. Bark, ntfy, and Gotify validate destination URLs. MQTT channel creation always blocks private, loopback, and link-local broker hosts; `MQTT_BLOCK_PRIVATE_NETWORKS` only affects the dispatch-time MQTT check.

Relays only fetch fixed upstream URLs. They do not fetch user-controlled provider URLs.

## Operational Hygiene

- Do not commit `.env` files or copied keys.
- Do not log raw auth headers, ingest keys, passwords, refresh tokens, or decrypted channel configs.
- Do not move frontend auth tokens into `localStorage`.

## Relay Threat Model Notes

1. Buffered raw ingest keys: relays must replay the original key to the next hop. Exposure is limited to pending buffers (Cloudflare Durable Object SQLite / EdgeOne KV), platform storage encryption, and successful forwarding deletes the record. Dead records redact `ingest_key` as `"[redacted]"`. Keep buffers draining normally and restrict KV/DO read access to the same trust level as `RELAY_ADMIN_TOKEN`.
2. Global primary-key idempotency oracle: an authenticated sender that guesses a UUID can learn `duplicate:true` if that id exists for any user. Accepted because valid ids are random UUIDv4 values, `user_id` always comes from the authenticated endpoint, and no cross-user reads or writes result. Herald does not split idempotency scope per tenant.
3. Single worker instance assumption: stale `sending` sweep plus multiple active workers can double-send. Production compose runs a single `worker`; do not scale it horizontally until delivery claims include an instance identifier.
