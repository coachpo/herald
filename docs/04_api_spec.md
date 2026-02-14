# API spec — Beacon Spear v0.1

This document describes HTTP endpoints at a high level. The app will expose:

- **Dashboard UI** (Next.js) under `/`
- **Backend JSON API** under `/api/...`
- **Ingest API** under `/api/ingest/{token}` (public, token-authenticated)

## Auth (backend JSON)

Backend uses Django sessions (cookie-based). State-changing requests require CSRF, except ingest.

Recommended endpoints:

- `GET /api/auth/csrf` — sets `csrftoken` cookie (and may return a token value)
- `POST /api/auth/signup` — create account + send verification email
- `POST /api/auth/login` — set session cookie
- `POST /api/auth/logout` — clear session
- `GET /api/auth/me` — current user + verification status
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

All endpoints require session auth and verified email (for mutating actions).

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

### Channels (Bark)

- `GET /api/channels`
- `POST /api/channels` (type=bark)
- `GET /api/channels/{id}`
- `PATCH /api/channels/{id}`
- `DELETE /api/channels/{id}`

### Rules

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{id}`
- `PATCH /api/rules/{id}`
- `DELETE /api/rules/{id}`
- `POST /api/rules/{id}/test`
  - body: sample message payload + endpoint id
  - returns: whether it matches and the rendered Bark request JSON (without sending)

### Deliveries (optional endpoints)

- `GET /api/messages/{id}/deliveries`

## Template rendering (proposed)

Rule’s `bark_payload_template_json` supports templating in string values:

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
