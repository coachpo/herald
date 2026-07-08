# Data Model

All primary keys are UUIDs. The initial schema is `backend/migrations/0001_initial.sql`.

## Tables

### `users`

- `id`, `email`, `password`, `is_active`, `created_at`

### `refresh_tokens`

- `id`, `user_id`, `token_hash`, `family_id`, `replaced_by_id`
- `created_at`, `updated_at`, `last_used_at`, `expires_at`
- `revoked_at`, `revoked_reason`, `ip`, `user_agent`

Refresh tokens are stored only as hashes. Token-family replay revokes the whole family.

### `ingest_endpoints`

- `id`, `user_id`, `name`, `token_hash`, `key_sha256`
- `created_at`, `revoked_at`, `deleted_at`, `last_used_at`

`token_hash` is the backend HMAC digest. `key_sha256` is exported to relays for offline endpoint-key checks.

### `messages`

- `id`, `user_id`, `ingest_endpoint_id`, `received_at`
- `title`, `body`, `group`, `priority`, `tags_json`, `url`, `extras_json`
- `content_type`, `body_sha256`, `headers_json`, `query_json`
- `remote_ip`, `user_agent`, `relay_via`, `deleted_at`

Message ids may be minted by relays. Backend insert is idempotent on the primary key.

### `channels`

- `id`, `user_id`, `type`, `name`, `config_json_encrypted`, `created_at`, `disabled_at`

Channel configs are encrypted at rest.

### `rules`

- `id`, `user_id`, `name`, `enabled`, `filter_json`
- `channel_id`, `payload_template_json`, `created_at`, `updated_at`

Delivery matching applies body contains/regex, priority range, and exact group filters. The rule UI and preview APIs also accept endpoint-id and tag filters, but the live ingest enqueue path does not currently pass endpoint id or tags into the matcher.

### `deliveries`

- `id`, `user_id`, `message_id`, `rule_id`, `channel_id`
- `status`, `attempt_count`, `next_attempt_at`, `sent_at`
- `last_error`, `provider_response_json`, `created_at`, `updated_at`

Delivery rows are both queue state and delivery history.
