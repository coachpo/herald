# API Guide

[openapi.yaml](openapi.yaml) is a checked-in generated schema snapshot; the running FastAPI app exposes its current schema at `/openapi.json`. This guide adds the details handled manually in route code, such as ingest body validation and provider config constraints. Route declarations and Pydantic schemas in [backend/routes](../backend/routes/) and [backend/schemas](../backend/schemas/) define the implementation; there is no repository schema-generation/check command configured.

## Auth

Protected dashboard APIs use `Authorization: Bearer <access token>`. Signup, login, refresh, and logout do not require an access token; refresh/logout send the refresh token in JSON. See [auth storage and revocation](06_security_privacy.md#auth) for the token lifecycle and browser-storage contract.

Endpoints:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/change-email`
- `POST /api/auth/change-password`
- `POST /api/auth/delete-account`

Password recovery is an [operator CLI action](07_operations.md#admin-tasks), not an HTTP endpoint.

## Ingest

```http
POST /api/ingest/{endpoint_id}
Content-Type: application/json
X-Herald-Ingest-Key: <raw key>
```

Allowed fields: `body` (required), `title`, `group`, `priority`, `tags`, `url`, `extras`.

The endpoint id accepts dashed UUIDs or dashless hex. Authentication requires an existing, non-revoked, non-deleted endpoint belonging to an active user. Requests must be UTF-8 JSON objects, at most 1 MiB; authentication occurs before body parsing.

Validation:

- `body` must be a non-blank string. `title` and `group`, when not null, must be strings.
- `priority` defaults to `3` and must be an integer-valued JSON number from `1` to `5`; `3.0` is accepted and normalized to `3`.
- `tags` must be an array of strings.
- `url`, when non-empty, must be `http` or `https`.
- `extras` must be an object with string values.
- Unknown top-level fields are rejected.

Relay headers:

- `X-Herald-Message-Id`
- `X-Herald-Received-At`
- `X-Herald-Relay-Via`

An invalid message UUID returns `422`. A valid UUID is used as the global idempotency key; a duplicate returns the supplied id without inserting another message or deliveries, even if it belongs to another endpoint/user. Receive timestamps are used only if parseable and within 48 hours of backend time; naive timestamps are interpreted as UTC, and invalid/out-of-range values fall back to backend time. Relay-via is lowercased, restricted to letters and commas, and capped at 64 characters.

Responses:

- `201 {"message_id":"..."}` for a new message.
- `200 {"message_id":"...","duplicate":true}` for a replayed relay id.
- `400`, `401`, `403`, `413`, `415`, `422`, or `429` for invalid or rate-limited requests.

Ingest and selected auth routes have in-process token-bucket limits. The `429` response is `{"detail":"rate_limited"}` with `Retry-After: 60`; these limits are not shared across API processes. See [configuration](07_operations.md#environment) for settings.

## Dashboard Resources

### Ingest Endpoints

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints`
- `GET /api/ingest-endpoints/{endpoint_id}`
- `PATCH /api/ingest-endpoints/{endpoint_id}`
- `POST /api/ingest-endpoints/{endpoint_id}/revoke`
- `DELETE /api/ingest-endpoints/{endpoint_id}`

### Messages

- `GET /api/messages`
- `GET /api/messages/{message_id}`
- `DELETE /api/messages/{message_id}`
- `POST /api/messages/batch-delete`
- `GET /api/messages/{message_id}/deliveries`

`GET /api/messages` accepts `ingest_endpoint_id`, `priority_min`, `priority_max`, `from`, and `to`. `POST /api/messages/batch-delete` requires `older_than_days` and accepts `ingest_endpoint_id`.

The list returns at most 500 non-deleted messages, newest first; it has no pagination parameters. `from` and `to` use inclusive ISO datetime bounds; unparseable values are ignored. Single and batch deletion are soft deletion, not payload erasure or cancellation of queued delivery. See [deletion relationships](03_data_model.md#deletion-and-relationships).

### Channels

- `GET /api/channels`
- `POST /api/channels`
- `DELETE /api/channels/{channel_id}`
- `POST /api/channels/{channel_id}/test`

Channel config fields:

- Bark: `server_base_url`, either `device_key` or `device_keys`, optional `default_payload_json`. A pasted Bark key URL is normalized.
- ntfy: `server_base_url`, `topic`, optional `access_token` or `username` plus `password`, optional `default_headers_json`.
- MQTT: `broker_host`, `topic`, optional `broker_port`, `username` plus `password`, `tls`, `tls_insecure`, `qos` 0-2, `retain`, `client_id`, and `keepalive_seconds`.
- Gotify: `server_base_url`, `app_token`, optional `default_priority` 0-10, `default_extras_json`, and `default_payload_json`.

Unknown channel-config fields are rejected. ntfy accepts either token auth or a complete username/password pair, not both; MQTT username/password must be supplied together. Channel creation and provider dispatch apply [outbound safety checks](06_security_privacy.md#outbound-safety). The create response includes normalized config; list responses omit it, and there is no channel-update or config-read endpoint. Channel tests perform a real provider send; rule tests below only preview.

### Rules

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{rule_id}`
- `PATCH /api/rules/{rule_id}`
- `DELETE /api/rules/{rule_id}`
- `POST /api/rules/test`
- `POST /api/rules/{rule_id}/test`

Rules store arbitrary JSON objects in `filter` and `payload_template`; nested filter shapes are not validated as a typed rule language. `PATCH` requires the same complete fields as create (`name`, `enabled`, `channel_id`), rather than applying a partial update.

Matching behavior in [core/rules.py](../backend/core/rules.py):

- `filter.body.contains`: case-insensitive match of any non-empty entry; `filter.body.regex`: case-insensitive Python regex (an invalid regex does not match).
- `filter.priority.min` / `max`: inclusive priority bounds; `filter.group`: exact, case-sensitive group equality.
- `filter.ingest_endpoint_ids`: endpoint membership; non-empty `filter.tags`: case-insensitive overlap with any tag. **Current live-ingest limitation:** [services/ingest.py](../backend/services/ingest.py) supplies no `ingest_endpoint_id` and uses `tags` where the matcher expects `tags_json`. Consequently an endpoint filter containing normal endpoint ids or a non-empty tag filter prevents live matching; these filters are not silently ignored.

Preview/test routes require an active endpoint owned by the caller and construct the endpoint/tag fields expected by the matcher. They do not enqueue or send notifications, and can report a match that live ingestion will not produce. Use body, priority, or group filters for live delivery until the context mismatch is fixed.

Templates recursively substitute `{{message.body}}`-style dotted paths in strings; missing values become empty strings, and substitution does not evaluate code. [core/template.py](../backend/core/template.py) defines context fields. **Current delivery limitation:** [worker.py](../backend/worker.py) passes title/body/group/priority/url and endpoint name, but omits message id/receive time/request metadata/endpoint id and supplies tags/extras under names the template builder does not read. Those other values are empty during live rendering, even when populated in preview. MQTT dispatch sends the original message body and does not apply `payload_template`. Bark-specific merging is documented in [Bark Provider Notes](08_bark_v2.md).

## Edge Config

`GET /api/edge-config` requires `Authorization: Bearer $EDGE_SYNC_TOKEN`. It returns `version`, `updated_at`, and `ingest_endpoints`, where each active endpoint item contains only `id` and `key_sha256`.

When `EDGE_SYNC_TOKEN` is unset the endpoint returns `404`; an incorrect token returns `401`. Export includes only non-revoked, non-deleted endpoints of active users. `version` is derived from that endpoint list, while `updated_at` is the export time. Synchronization is an explicit [operations task](07_operations.md#admin-tasks), not an automatic effect of endpoint creation/revocation.
