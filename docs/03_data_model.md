# Data Model

## Core Principles

- All primary keys are UUID v4.
- Message and endpoint deletion is soft-delete in the user-facing API.
- Channel configs are encrypted at rest.
- Many structured fields are stored in JSON columns with `_json` suffixes.

## Users And Auth Tokens

### `users`

- `id`
- `email` (case-insensitive unique)
- `password`
- `email_verified_at`
- `is_active`
- `is_staff`
- `created_at`

### `email_verification_tokens`

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `used_at`
- `created_at`

### `password_reset_tokens`

- `id`
- `user_id`
- `token_hash`
- `expires_at`
- `used_at`
- `created_at`

### `refresh_tokens`

- `id`
- `user_id`
- `token_hash`
- `family_id`
- `replaced_by`
- `created_at`
- `updated_at`
- `last_used_at`
- `expires_at`
- `revoked_at`
- `revoked_reason`
- `ip`
- `user_agent`

Notes:

- Refresh tokens are opaque secrets stored only as hashes.
- `family_id` is used to revoke a whole token family on replay/reuse.

## Ingest Endpoints

### `ingest_endpoints`

- `id`
- `user_id`
- `name`
- `token_hash`
- `created_at`
- `revoked_at`
- `deleted_at`
- `last_used_at`

Notes:

- `token_hash` is unique.
- Revoked or deleted endpoints cannot ingest.

## Messages

### `messages`

- `id`
- `user_id`
- `ingest_endpoint_id`
- `received_at`
- `title`
- `body`
- `group`
- `priority`
- `tags_json`
- `url`
- `extras_json`
- `content_type`
- `body_sha256`
- `headers_json`
- `query_json`
- `remote_ip`
- `user_agent`
- `deleted_at`

Notes:

- `body` is required; all other payload fields are optional.
- `headers_json` stores redacted header values.
- `extras_json` is a flat object of string values.

## Channels

### `channels`

- `id`
- `user_id`
- `type` (`bark`, `ntfy`, `mqtt`)
- `name`
- `config_json_encrypted`
- `created_at`
- `disabled_at`

Logical config fields:

- Bark: `server_base_url`, `device_key` or `device_keys`, `default_payload_json`
- ntfy: `server_base_url`, `topic`, optional bearer/basic auth, `default_headers_json`
- MQTT: `broker_host`, `broker_port`, `topic`, optional auth/TLS/QoS/retain/client_id/keepalive_seconds`

## Forwarding Rules

### `forwarding_rules`

- `id`
- `user_id`
- `name`
- `enabled`
- `filter_json`
- `channel_id`
- `payload_template_json`
- `created_at`
- `updated_at`

Supported filter dimensions:

- `ingest_endpoint_ids`
- `body.contains`
- `body.regex`
- `priority.min` / `priority.max`
- `tags`
- `group`

## Deliveries

### `deliveries`

- `id`
- `user_id`
- `message_id`
- `rule_id`
- `channel_id`
- `status` (`queued`, `sending`, `retry`, `sent`, `failed`)
- `attempt_count`
- `next_attempt_at`
- `sent_at`
- `last_error`
- `provider_response_json`
- `created_at`
- `updated_at`

Notes:

- These rows are both queue state and delivery history.
- Backend worker owns retry/backoff behavior.

## Deletion Semantics

- Endpoint archive: sets `revoked_at` and `deleted_at`
- Message delete: sets `deleted_at`
- Channel and rule delete endpoints remove the row
- Account delete removes the user and cascades owned data
