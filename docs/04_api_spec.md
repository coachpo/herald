# API Guide

`docs/openapi.yaml` is the schema source of truth. This file is the human-readable overview of the same API.

## Authentication

### Dashboard APIs

- Access token via `Authorization: Bearer <token>`
- Refresh token sent in JSON body to `POST /api/auth/refresh`
- Browser requests use `credentials: "omit"`
- Unverified users can log in and read, but unsafe resource methods are blocked

### Ingest API

- `POST /api/ingest/{endpoint_id}`
- Header: `X-Herald-Ingest-Key`
- Accepts dashed UUID and dashless hex endpoint IDs

## Auth Endpoints

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/resend-verification`
- `POST /api/auth/verify-email`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- `POST /api/auth/change-email`
- `POST /api/auth/change-password`
- `POST /api/auth/delete-account`

Behavior notes:

- Signup can be disabled by backend settings.
- Refresh token rotation is mandatory; clients must store the newest refresh token returned.
- Password reset and password change revoke all refresh tokens.

## Ingest Contract

### Endpoint

- `POST /api/ingest/{endpoint_id}`

### Required request shape

- `Content-Type: application/json`
- JSON object
- `body` must be a non-empty string

### Optional fields

- `title`
- `group`
- `priority` (1-5, default 3)
- `tags` (array of strings)
- `url` (valid URL string)
- `extras` (object of string values)

### Validation and errors

- `400` for invalid UTF-8 or invalid JSON
- `401` for unknown endpoint, missing key, wrong key, revoked endpoint, or deleted endpoint
- `403` when the endpoint's user is inactive or ingest is blocked for unverified email
- `413` for payloads above configured size
- `415` for non-JSON content types
- `422` for schema/validation failures such as missing `body` or unknown top-level keys

### Success response

- `201` with `{ "message_id": "..." }`

## Resource APIs

### Ingest endpoints

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints`
- `POST /api/ingest-endpoints/{id}/revoke`
- `DELETE /api/ingest-endpoints/{id}`

`POST` returns the ingest key once together with the created endpoint and canonical ingest URL.

### Messages

- `GET /api/messages`
- `GET /api/messages/{id}`
- `DELETE /api/messages/{id}`
- `POST /api/messages/batch-delete`
- `GET /api/messages/{id}/deliveries`

Supported list filters:

- `ingest_endpoint_id`
- `q`
- `group`
- `priority_min`
- `priority_max`
- `tag`
- `from`
- `to`

### Channels

- `GET /api/channels`
- `POST /api/channels`
- `GET /api/channels/{id}`
- `PATCH /api/channels/{id}`
- `DELETE /api/channels/{id}`
- `POST /api/channels/{id}/test`

### Channel Configs

Channel creation and updates require a `config` object specific to the provider type.

#### Bark
```json
{
  "server_base_url": "https://api.day.app",
  "device_key": "your_key",
  "default_payload_json": { "sound": "glass" }
}
```

#### ntfy
```json
{
  "server_base_url": "https://ntfy.sh",
  "topic": "your_topic",
  "default_headers_json": { "Priority": "high" }
}
```

#### MQTT
```json
{
  "broker_host": "broker.emqx.io",
  "broker_port": 1883,
  "topic": "herald/messages"
}
```

#### Gotify
```json
{
  "server_base_url": "https://gotify.example.com",
  "app_token": "Apx...",
  "default_priority": 5,
  "default_extras_json": {
    "client::display": { "contentType": "text/markdown" }
  }
}
```


Channel test sends immediately and returns provider metadata. It does not create a stored message or delivery row.

### Rules

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{id}`
- `PATCH /api/rules/{id}`
- `DELETE /api/rules/{id}`
- `POST /api/rules/test`
- `POST /api/rules/{id}/test`

Rule test endpoints only evaluate filters and render payload previews. They do not dispatch notifications.

## Template Variables

Templates can reference:

- `{{message.id}}`, `{{message.received_at}}`, `{{message.title}}`, `{{message.body}}`
- `{{message.group}}`, `{{message.priority}}`, `{{message.tags}}`, `{{message.url}}`
- `{{message.extras.<key>}}`
- `{{request.content_type}}`, `{{request.remote_ip}}`, `{{request.user_agent}}`
- `{{request.headers.<name>}}`, `{{request.query.<name>}}`
- `{{ingest_endpoint.id}}`, `{{ingest_endpoint.name}}`

Rendering rules:

- Missing values render as empty strings
- Priority renders as a string in template output
- Tags render as a comma-joined string

## Health And Edge Snapshot

- Backend health: `GET /health`
- Edge-lite health: `GET /healthz`
- Edge snapshot export: `GET /api/edge-config`

`GET /api/edge-config` returns active ingest endpoints plus Bark/ntfy/gotify channels and rules for edge-lite consumption. MQTT is excluded.
