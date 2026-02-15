# API spec — Beacon Spear v0.2

This document describes HTTP endpoints at a high level. The app will expose:

- **Dashboard UI** (Next.js) under `/`
- **Backend JSON API** under `/api/...`
- **Ingest API** under `/api/ingest/{token}` (public, token-authenticated)

## Auth (backend JSON, JWT)

Backend uses JWT access tokens for authenticated endpoints.

- Authenticated requests must include:
  - `Authorization: Bearer <access_token>`
- The backend does **not** use Django session cookies for auth.

Recommended endpoints:

- `POST /api/auth/signup` — create account + send verification email
- `POST /api/auth/login` — returns access JWT; sets refresh token cookie
- `POST /api/auth/refresh` — returns new access JWT (uses refresh cookie)
- `POST /api/auth/logout` — revokes refresh token; clears refresh cookie
- `GET /api/auth/me` — current user + verification status (requires Authorization)
- `POST /api/auth/resend-verification` — send a new verification email (rate limited)
- `POST /api/auth/verify-email` — verify using one-time token
- `POST /api/auth/forgot-password` — send reset email (rate limited)
- `POST /api/auth/reset-password` — set new password using one-time token
- `POST /api/auth/change-email` — change email + re-verify
- `POST /api/auth/change-password` — change password

## Auth (dashboard routes)

Dashboard pages are implemented in Next.js (paths are suggested):

- `/signup`, `/login`, `/forgot-password`
- `/verify-email?token=...`
- `/reset-password?token=...`

## Ingest API

### POST /api/ingest/{token}

- Auth: ingest endpoint token
- Body: arbitrary UTF‑8 text
- Limits:
  - `Content-Length` must be ≤ 1MB when present
  - if absent, read up to 1MB+1; reject if exceeded
  - reject invalid UTF‑8
- Stores:
  - payload text
  - content type
  - query params
  - remote IP/user agent
  - headers (redacted)
- Response:
  - `201 Created` with `{ "message_id": "..." }`
- Errors:
  - `401` invalid token / revoked
  - `403` user not verified or disabled (if enforced)
  - `413` payload too large
  - `400` invalid UTF‑8

## App JSON API (authenticated)

All endpoints (except ingest and auth endpoints as noted) require:

- `Authorization: Bearer <access_token>`
- verified email (for mutating actions)

### Ingest endpoints

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints` → returns token once
- `POST /api/ingest-endpoints/{id}/revoke`

### Messages

- `GET /api/messages`
  - filters: `ingest_endpoint_id`, `q` (substring), `from`, `to`
- `GET /api/messages/{id}`
- `DELETE /api/messages/{id}`
- `POST /api/messages/batch-delete`
  - body: `{ "older_than_days": 30, "ingest_endpoint_id": "..."? }`

### Channels (bark/ntfy/mqtt)

- `GET /api/channels`
- `POST /api/channels` (type=bark|ntfy|mqtt)
- `GET /api/channels/{id}`
- `PATCH /api/channels/{id}`
  - `DELETE /api/channels/{id}`

Request shape:

```json
{
  "type": "bark|ntfy|mqtt",
  "name": "...",
  "config": {
    "...": "type-specific"
  }
}
```

Notes:

- `PATCH /api/channels/{id}` requires `type` to match the existing channel.
- `config` validation depends on `type`.

### Rules

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{id}`
- `PATCH /api/rules/{id}`
- `DELETE /api/rules/{id}`
- `POST /api/rules/{id}/test`
  - body: sample message payload + endpoint id
  - returns: whether it matches, the channel type, and the rendered payload template (without sending)

### Deliveries (optional endpoints)

- `GET /api/messages/{id}/deliveries`

## Template rendering (proposed)

Rule’s `payload_template_json` supports templating in string values (legacy: `bark_payload_template_json`):

Available variables:

- `{{message.id}}`
- `{{message.received_at}}`
- `{{message.payload_text}}`
- `{{message.content_type}}`
- `{{ingest_endpoint.name}}`
- `{{ingest_endpoint.id}}`

Example:

```
{
  "title": "Ingest {{ingest_endpoint.name}}",
  "body": "{{message.payload_text}}"
}
```

## Bark v2 forwarding contract

For each delivery, worker performs:

- `POST {server_base_url}/push`
- `Content-Type: application/json`
- JSON payload is built as:
  1) start with rule’s rendered JSON
  2) merge channel `default_payload_json` (if defined) and rule JSON (rule wins)
  3) inject `device_key` (or `device_keys`) from channel config

UI must use the same JSON field names as Bark v2.

## ntfy forwarding contract

Worker performs:

- `POST {server_base_url}/{topic}`
- Request body: rendered template `body` (falls back to message payload text)
- Headers can be driven by template keys (e.g. `Title`, `Tags`, `Priority`) and merged with channel `default_headers_json`.

## MQTT forwarding contract

Worker performs:

- publish to broker `{broker_host}:{broker_port}` on `topic`
- Payload is derived from rendered template:
  - if template renders an object with `body`/`payload`/`message`, use that value
  - otherwise, publish the rendered object (JSON-encoded) or string
