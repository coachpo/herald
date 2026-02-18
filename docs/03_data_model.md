# Data model — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

This doc defines the logical schema. Implementation may use Django models + migrations.

## Users

`users`

- `id` (uuid or bigint)
- `email` (unique, case-insensitive)
- `password_hash`
- `email_verified_at` (nullable)
- `created_at`
- `last_login_at`
- `is_active`

Related:

- `email_verification_tokens(user_id, token_hash, expires_at, used_at)`
- `password_reset_tokens(user_id, token_hash, expires_at, used_at)`
- `refresh_tokens(user_id, token_hash, expires_at, revoked_at, last_used_at)`

Notes:

- Refresh tokens are long-lived opaque secrets stored hashed at rest.
- Multiple refresh tokens per user are allowed to support multiple devices/browsers.

## Ingest endpoints

`ingest_endpoints`

- `id`
- `user_id` (FK)
- `name`
- `token_hash` (store hash only; token shown once at create time)
- `created_at`
- `revoked_at` (nullable)
- `deleted_at` (nullable; archived endpoints)
- `last_used_at` (nullable)

Indexes:

- `(user_id)`
- `(token_hash)` unique

## Messages (immutable after ingest)

`messages`

- `id`
- `user_id` (FK)
- `ingest_endpoint_id` (FK)
- `received_at`
- `title` (string; nullable) — notification title
- `body` (text; required) — main notification content
- `group` (string; nullable) — grouping identifier
- `priority` (integer 1–5; default 3) — 1=lowest, 5=critical
- `tags` (JSON array of strings; default `[]`)
- `url` (string; nullable) — action URL
- `extras_json` (JSON object; default `{}`) — arbitrary key-value pairs (string values)
- `content_type` (nullable) — original request Content-Type
- `body_sha256` (optional; hash of `body` field for dedupe/debug)
- `headers_json` (JSON; sensitive values redacted)
- `query_json` (JSON)
- `remote_ip` (string)
- `user_agent` (string; nullable)
- `deleted_at` (nullable)

Indexes:

- `(user_id, received_at desc)`
- `(user_id, ingest_endpoint_id, received_at desc)`
- `(user_id, group)` — for group-based queries
- `(user_id, priority)` — for priority-based filtering
- Optional: `(user_id, body_sha256)`

Notes:

- Deletion: soft-delete (`deleted_at`), hiding from normal views.
- `extras_json` values must be strings. Nested objects are not supported.
- `tags` is stored as a JSON array; filtering uses array containment.

## Channels

`channels`

- `id`
- `user_id` (FK)
- `type` (enum; `bark`, `ntfy`, `mqtt`)
- `name`
- `config_json_encrypted` (text/blob; encrypted at rest)
- `created_at`
- `disabled_at` (nullable)

### Bark config (logical)

Stored inside `config_json_encrypted`:

- `server_base_url` (string; example `https://your-bark.example.com`)
- `device_key` (string) OR `device_keys` (array of strings) — optional to support Bark multi-device
- `default_payload_json` (object) — extra Bark v2 fields to merge into every request (optional)

### ntfy config (logical)

Stored inside `config_json_encrypted`:

- `server_base_url` (string; example `https://ntfy.sh`)
- `topic` (string)
- auth (choose one):
  - `access_token` (string)
  - `username` + `password` (strings)
- `default_headers_json` (object) — extra HTTP headers merged into every publish (optional)

### MQTT config (logical)

Stored inside `config_json_encrypted`:

- `broker_host` (string)
- `broker_port` (int; default 1883)
- `topic` (string)
- optional auth: `username` + `password`
- optional TLS: `tls` (bool), `tls_insecure` (bool)
- optional publish tuning: `qos` (0-2), `retain` (bool), `client_id` (string), `keepalive_seconds` (int)

## Forwarding rules

`forwarding_rules`

- `id`
- `user_id` (FK)
- `name`
- `enabled` (bool)
- `filter_json` (JSON)
- `channel_id` (FK)
- `payload_template_json` (JSON; nullable) — template for all channel types
- `created_at`
- `updated_at`

### Filter JSON

```
{
  "ingest_endpoint_ids": ["ep_1", "ep_2"],   // optional; message endpoint must be in set
  "body": {
    "contains": ["error", "panic"],          // optional, case-insensitive substring match (any)
    "regex": "timeout\\b"                    // optional, regex match on body
  },
  "priority": {
    "min": 3,                                // optional; message priority >= min
    "max": 5                                 // optional; message priority <= max
  },
  "tags": ["deploy", "critical"],            // optional; message must have at least one of these tags (any-of)
  "group": "production"                      // optional; exact match on message group
}
```

Semantics:

- If `ingest_endpoint_ids` provided: message's endpoint must be in the set.
- If `body.contains` provided: at least one substring must be present in body (case-insensitive).
- If `body.regex` provided: regex must match body.
- If `priority.min` and/or `priority.max` provided: message priority must be within range.
- If `tags` provided: message must have at least one matching tag (any-of).
- If `group` provided: message group must match exactly.
- All provided conditions must match (AND across dimensions).

## Deliveries (queue + history)

`deliveries`

- `id`
- `user_id` (FK)
- `message_id` (FK)
- `rule_id` (FK)
- `channel_id` (FK)
- `status` (enum: `queued`, `sending`, `retry`, `sent`, `failed`)
- `attempt_count` (int)
- `next_attempt_at` (timestamp)
- `sent_at` (nullable)
- `last_error` (text; nullable)
- `provider_response_json` (JSON; nullable)
- `created_at`
- `updated_at`

Indexes:

- `(status, next_attempt_at)`
- `(message_id)`
- `(user_id, created_at desc)`

## Data retention / deletion

- Default: store indefinitely.
- User deletion:
  - single message delete sets `deleted_at`
  - batch delete sets `deleted_at` for all qualifying messages
- Optional later: hard-delete to remove rows permanently.
