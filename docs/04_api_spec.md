# API Guide

`docs/openapi.yaml` is generated from the FastAPI app. This guide adds the details that are handled manually in route code, such as ingest body validation and provider config constraints.

## Auth

Protected dashboard APIs use `Authorization: Bearer <access token>`. Signup, login, refresh, and logout do not require an access token; refresh/logout send the refresh token in JSON. The frontend stores refresh tokens in `sessionStorage` and access tokens in React state.

Endpoints:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/change-email`
- `POST /api/auth/change-password`
- `POST /api/auth/delete-account`

Password recovery is an operator CLI action: `herald-backend reset-password <email>`.

## Ingest

```http
POST /api/ingest/{endpoint_id}
Content-Type: application/json
X-Herald-Ingest-Key: <raw key>
```

Allowed fields: `body` (required), `title`, `group`, `priority`, `tags`, `url`, `extras`.

Validation:

- `body` must be a non-empty string.
- `priority` defaults to `3` and must be an integer-valued JSON number from `1` to `5`; `3.0` is accepted and normalized to `3`.
- `tags` must be an array of strings.
- `url`, when non-empty, must be `http` or `https`.
- `extras` must be an object with string values.
- Unknown top-level fields are rejected.

Relay headers:

- `X-Herald-Message-Id`
- `X-Herald-Received-At`
- `X-Herald-Relay-Via`

Responses:

- `201 {"message_id":"..."}` for a new message.
- `200 {"message_id":"...","duplicate":true}` for a replayed relay id.
- `400`, `401`, `403`, `413`, `415`, `422`, or `429` for invalid or rate-limited requests.

## Dashboard Resources

Ingest endpoints:

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints`
- `GET /api/ingest-endpoints/{endpoint_id}`
- `PATCH /api/ingest-endpoints/{endpoint_id}`
- `POST /api/ingest-endpoints/{endpoint_id}/revoke`
- `DELETE /api/ingest-endpoints/{endpoint_id}`

Messages:

- `GET /api/messages`
- `GET /api/messages/{message_id}`
- `DELETE /api/messages/{message_id}`
- `POST /api/messages/batch-delete`
- `GET /api/messages/{message_id}/deliveries`

`GET /api/messages` accepts `ingest_endpoint_id`, `priority_min`, `priority_max`, `from`, and `to`. `POST /api/messages/batch-delete` requires `older_than_days` and accepts `ingest_endpoint_id`.

Channels:

- `GET /api/channels`
- `POST /api/channels`
- `DELETE /api/channels/{channel_id}`
- `POST /api/channels/{channel_id}/test`

Channel config fields:

- Bark: `server_base_url`, either `device_key` or `device_keys`, optional `default_payload_json`. A pasted Bark key URL is normalized.
- ntfy: `server_base_url`, `topic`, optional `access_token` or `username` plus `password`, optional `default_headers_json`.
- MQTT: `broker_host`, `topic`, optional `broker_port`, `username` plus `password`, `tls`, `tls_insecure`, `qos` 0-2, `retain`, `client_id`, and `keepalive_seconds`.
- Gotify: `server_base_url`, `app_token`, optional `default_priority` 0-10, `default_extras_json`, and `default_payload_json`.

Rules:

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{rule_id}`
- `PATCH /api/rules/{rule_id}`
- `DELETE /api/rules/{rule_id}`
- `POST /api/rules/test`
- `POST /api/rules/{rule_id}/test`

Rules store arbitrary JSON in `filter` and `payload_template`. Live delivery matching applies `filter.body.contains`, `filter.body.regex`, `filter.priority.min`, `filter.priority.max`, and exact `filter.group`. The UI can also write `filter.ingest_endpoint_ids` and `filter.tags`; preview/test routes build endpoint and tag context for those filters, but the current live ingest enqueue path does not pass endpoint id or tags into the matcher.

## Edge Config

`GET /api/edge-config` requires `Authorization: Bearer $EDGE_SYNC_TOKEN`. It returns `version`, `updated_at`, and `ingest_endpoints`, where each active endpoint item contains only `id` and `key_sha256`.
