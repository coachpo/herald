# API spec — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

This document describes HTTP endpoints at a high level. The app will expose:

- **Dashboard UI** (Next.js) under `/`
- **Backend JSON API** under `/api/...`
- **Ingest API** under `/api/ingest/{endpoint_id}` (public, header-authenticated)

## Auth (backend JSON, JWT)

Backend uses JWT access tokens for authenticated endpoints.

- Authenticated requests must include:
  - `Authorization: Bearer <access_token>`
- The backend does **not** use Django session cookies for auth.

Recommended endpoints:

- `POST /api/auth/signup` — create account + send verification email
- `POST /api/auth/login` — returns access JWT + refresh token
- `POST /api/auth/refresh` — body `{ "refresh_token": "..." }` → returns new access JWT + refresh token (refresh token rotation)
- `POST /api/auth/logout` — body `{ "refresh_token": "..." }` (optional) → revokes refresh token; client can also drop tokens locally
- `GET /api/auth/me` — current user + verification status (requires Authorization)
- `POST /api/auth/resend-verification` — send a new verification email (rate limited)
- `POST /api/auth/verify-email` — verify using one-time token
- `POST /api/auth/forgot-password` — send reset email (rate limited)
- `POST /api/auth/reset-password` — set new password using one-time token
- `POST /api/auth/change-email` — change email + re-verify
- `POST /api/auth/change-password` — change password
- `POST /api/auth/delete-account` — permanently delete account

## Auth (dashboard routes)

Dashboard pages are implemented in Next.js (paths are suggested):

- `/signup`, `/login`, `/forgot-password`
- `/verify-email?token=...`
- `/reset-password?token=...`

## Ingest API

### POST /api/ingest/{endpoint_id}

- Auth:
  - required header: `X-Beacon-Ingest-Key: <ingest_key>`
  - endpoint identified by path parameter `{endpoint_id}`
  - canonical URL form uses a dashless UUID (32 hex chars); the server also accepts dashed UUIDs
- Content-Type: `application/json` required (reject with `415` otherwise)
- Body: structured JSON object
- Required fields:
  - `body` (string) — main notification content; must be non-empty
- Optional fields:
  - `title` (string) — notification title
  - `group` (string) — grouping identifier for organizing notifications
  - `priority` (integer 1–5; default 3) — 1=lowest, 2=low, 3=normal, 4=high, 5=critical
  - `tags` (array of strings; default `[]`) — labels/categories for filtering
  - `url` (string) — action URL (must be a valid URL if provided)
  - `extras` (object with string values; default `{}`) — arbitrary key-value pairs for custom data
- Unknown top-level keys are rejected with `422`.
- Limits:
  - `Content-Length` must be ≤ 1MB when present
  - if absent, read up to 1MB+1; reject if exceeded
- Stores:
  - structured fields (title, body, group, priority, tags, url, extras)
  - content type
  - query params
  - remote IP/user agent
  - headers (redacted)
- Response:
  - `201 Created` with `{ "message_id": "..." }`
- Errors:
  - `400` invalid JSON or invalid UTF-8
  - `401` auth failure (missing/invalid key, unknown/revoked endpoint)
  - `403` user not verified or disabled (if enforced)
  - `413` payload too large
  - `415` Content-Type is not `application/json`
  - `422` validation error (missing `body`, invalid `priority` range, unknown keys, etc.)

Example request:

```bash
curl -X POST https://example.com/api/ingest/abcdef1234567890abcdef1234567890 \
  -H "X-Beacon-Ingest-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Deploy failed",
    "body": "Production deploy #1234 failed at step 3",
    "group": "deploys",
    "priority": 4,
    "tags": ["deploy", "production", "failure"],
    "url": "https://ci.example.com/builds/1234",
    "extras": {
      "build_id": "1234",
      "environment": "production",
      "commit": "abc123f"
    }
  }'
```

Minimal request (only required field):

```bash
curl -X POST https://example.com/api/ingest/abcdef1234567890abcdef1234567890 \
  -H "X-Beacon-Ingest-Key: my-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"body": "Something happened"}'
```

## Optional edge forwarders

Edge forwarders (Cloudflare Workers / Tencent EdgeOne) can proxy the ingest API.

See `docs/10_edge.md`.

## App JSON API (authenticated)

All endpoints (except ingest and auth endpoints as noted) require:

- `Authorization: Bearer <access_token>`
- verified email (for mutating actions)

### Ingest endpoints

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints` → returns ingest key once
- `POST /api/ingest-endpoints/{id}/revoke`
- `DELETE /api/ingest-endpoints/{id}` (archive/hide)

### Messages

- `GET /api/messages`
  - filters: `ingest_endpoint_id`, `q` (substring on body), `group`, `priority_min`, `priority_max`, `tag`, `from`, `to`
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
- `POST /api/channels/{id}/test`
  - sends a test notification immediately (no ingest/worker)
  - body supports optional `title`, `body`, and `payload_json` (provider-specific)

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
- `POST /api/rules/test`
  - body: sample message payload + endpoint id
  - returns: which rules would trigger + rendered payload previews (without sending)
- `GET /api/rules/{id}`
- `PATCH /api/rules/{id}`
- `DELETE /api/rules/{id}`
- `POST /api/rules/{id}/test`
  - body: sample message payload + endpoint id
  - returns: whether it matches, the channel type, and the rendered payload template (without sending)

### Deliveries (optional endpoints)

- `GET /api/messages/{id}/deliveries`

## Template rendering

Rule's `payload_template_json` supports templating in string values.

Available variables:

### Message fields (from ingested payload)

- `{{message.id}}`
- `{{message.received_at}}` — ISO 8601 timestamp
- `{{message.title}}` — notification title (empty string if not provided)
- `{{message.body}}` — main notification content
- `{{message.group}}` — grouping identifier (empty string if not provided)
- `{{message.priority}}` — integer 1–5
- `{{message.tags}}` — comma-separated string of tags (e.g., `"deploy,production,failure"`)
- `{{message.url}}` — action URL (empty string if not provided)
- `{{message.extras.<key>}}` — arbitrary extras by key (e.g., `{{message.extras.build_id}}`)

### Request metadata (from the HTTP request)

- `{{request.content_type}}`
- `{{request.remote_ip}}`
- `{{request.user_agent}}`
- `{{request.headers.<name>}}` — request header by name (e.g., `{{request.headers.x-custom-header}}`); redacted headers return `[REDACTED]`
- `{{request.query.<name>}}` — query parameter by name (e.g., `{{request.query.source}}`)

### Ingest endpoint

- `{{ingest_endpoint.id}}`
- `{{ingest_endpoint.name}}`

### Rendering rules

- Missing/null variables render as empty string `""`.
- Variables are substituted as strings; no type coercion (priority renders as `"4"`, not integer `4`).
- Nested dot-notation is supported for `extras`, `headers`, and `query`.
- No conditional logic or filters (keep it simple).

Example:

```json
{
  "title": "[{{message.priority}}] {{message.title}}",
  "body": "{{message.body}}\n\nGroup: {{message.group}}\nSource: {{ingest_endpoint.name}}\nIP: {{request.remote_ip}}",
  "url": "{{message.url}}",
  "group": "{{message.group}}",
  "tags": "{{message.tags}}"
}
```

## Bark v2 forwarding contract

For each delivery, worker performs:

- `POST {server_base_url}/push`
- `Content-Type: application/json`
- JSON payload is built as:
  1) start with rule's rendered `payload_template_json`
  2) merge channel `default_payload_json` (if defined) — rule template wins on conflicts
  3) inject `device_key` (or `device_keys`) from channel config
  4) if template omits `body`, use `message.body`
  5) if template omits `title` and message has a title, use `message.title`

UI must use the same JSON field names as Bark v2.

## ntfy forwarding contract

Worker performs:

- `POST {server_base_url}/{topic}`
- Request body: rendered template `body` (falls back to `message.body`)
- Headers can be driven by template keys (e.g. `Title`, `Tags`, `Priority`) and merged with channel `default_headers_json`.
- If template omits `Title` and message has a title, use `message.title`.
- If template omits `Priority`, map `message.priority` to ntfy priority levels (1→min, 2→low, 3→default, 4→high, 5→urgent).
- If template omits `Tags` and message has tags, use `message.tags` (comma-separated).

## MQTT forwarding contract

Worker performs:

- publish to broker `{broker_host}:{broker_port}` on `topic`
- Payload is derived from rendered template:
  - if template renders an object with `body`/`payload`/`message`, use that value
  - otherwise, publish the rendered object (JSON-encoded) or string
  - if no template is defined, publish a JSON object with all message fields (title, body, group, priority, tags, url, extras)
