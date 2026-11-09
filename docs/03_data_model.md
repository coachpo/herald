# Data Model

Business-table primary keys are UUIDs. The schema is defined in [numbered SQL migrations](../backend/migrations/); currently there is one migration, [0001_initial.sql](../backend/migrations/0001_initial.sql). The migration runner also maintains `schema_migrations` with a text `version` primary key and `applied_at` timestamp. Runtime SQLAlchemy tables are reflected from this migrated schema, not declared as ORM models.

## Tables

### `users`

- `id`, `email`, `password` (PBKDF2-SHA256 hash), `is_active`, `created_at`

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

Message ids may be supplied through relay headers. Backend insert is idempotent on the global primary key, not scoped by user or endpoint; duplicates do not create additional delivery rows. See the [security limitations](06_security_privacy.md#relay-threat-model-notes).

### `channels`

- `id`, `user_id`, `type`, `name`, `config_json_encrypted`, `created_at`, `disabled_at`

Channel configs are encrypted at rest.

### `rules`

- `id`, `user_id`, `name`, `enabled`, `filter_json`
- `channel_id`, `payload_template_json`, `created_at`, `updated_at`

See [rule matching and preview limitations](04_api_spec.md#rules) for the current filter behavior.

### `deliveries`

- `id`, `user_id`, `message_id`, `rule_id`, `channel_id`
- `status`, `attempt_count`, `next_attempt_at`, `sent_at`
- `last_error`, `provider_response_json`, `created_at`, `updated_at`

Delivery rows are both queue state and delivery history.

## Deletion And Relationships

- Dependent business tables belong to a user through `user_id`; deleting an account physically deletes the user and cascades to its dependent rows.
- Endpoint deletion sets `deleted_at` and `revoked_at`; it retains existing messages. Message deletion and batch deletion set `messages.deleted_at`, rather than removing payloads or deliveries. Lists hide these messages, but owner-scoped detail/delivery routes still return them, and queued delivery is not canceled.
- Physical deletion of a channel cascades to its rules and related deliveries. Physical deletion of a rule cascades to its deliveries. Delivery history therefore does not survive all configuration deletions.
- There is no scheduled backend message-purge job in the repository. Soft deletion is not a retention or erasure guarantee; deployment-specific retention and backup obligations must be established separately.
