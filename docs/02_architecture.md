# Architecture — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

## High-level components

1) **Django backend**
   - JSON APIs for the dashboard
   - Ingest endpoint: `POST /api/ingest/{endpoint_id}` (canonical URL uses dashless UUID; requires `X-Beacon-Ingest-Key`)
   - Accepts structured JSON payloads (title, body, priority, tags, group, url, extras)
   - Email sending for verification + password reset (SMTP)
   - JWT auth for dashboard APIs (no Django session cookies)

2) **Next.js dashboard (latest stable)**
   - Web UI routes under `/`
   - Calls backend JSON APIs under `/api/*`

3) **Worker process**
    - Polls DB for due deliveries
    - Renders payload templates against rich message context (all structured fields + request metadata + extras)
    - Sends provider requests (Bark v2 HTTP, ntfy HTTP publish, MQTT publish)
    - Updates delivery status, schedules retries with exponential backoff

4) **Postgres**
   - Stores users, endpoints, messages, channels, rules, deliveries
   - Acts as the job queue (deliveries table)

## Authentication model

- Dashboard: JWT access token sent as `Authorization: Bearer <token>`
  - Backend issues short-lived access JWTs
  - Dashboard refreshes access tokens using a refresh token
- Ingest API: `endpoint_id` in URL path + `X-Beacon-Ingest-Key` header; no JWT required

## Deployment routing (simple)

To keep auth simple, host dashboard + backend on the **same origin**:

- `/api/*` → Django backend
- everything else → Next.js

This avoids cross-origin complexity for auth and keeps the mental model simple.

## JWT session strategy (recommended)

### Tokens

- **Access token (JWT)**: short-lived (e.g., 15 minutes), used for all authenticated `/api/*` calls.
- **Refresh token**: long-lived opaque token stored server-side (hashed) to support logout and rotation.

### Transport (recommended)

- Access JWT is returned in JSON and stored in memory by the dashboard.
- Refresh token is returned in JSON and stored client-side (recommended: `sessionStorage`, per-tab).

With this approach:

- Backend APIs authenticate requests via `Authorization` header (not cookies), so CSRF tokens are not required for state-changing requests.
- Refresh endpoint uses the refresh token in the request body and rotates it on every use.

## Email flows

### Email verification

1) User signs up with email+password.
2) System creates user with `email_verified_at = NULL`.
3) System emails a verification link (one-time token) that lands on the dashboard, which calls a backend verify API.
4) Backend sets `email_verified_at`.
5) Until verified, block:
   - creating ingest endpoints
   - creating channels
   - creating/enabling rules
   - ingest itself (optional; recommended to block to avoid abuse)

### Password reset

Standard Django-style flow:

1) User requests reset from “Forgot password”.
2) System emails a reset link with one-time token (dashboard page).
3) Dashboard calls backend reset API to set a new password.

## Message ingest flow

1) Request `POST /api/ingest/{endpoint_id}` (canonical URL uses dashless UUID)
2) Identify ingest endpoint by id; validate `X-Beacon-Ingest-Key` (constant-time compare against stored hash)
3) Enforce:
   - `Content-Type: application/json` required (reject with `415` otherwise)
   - body size ≤ 1MB (reject > 1MB with `413`)
   - valid JSON (reject with `400`)
   - valid UTF-8 (reject with `400`)
4) Parse and validate structured payload:
   - `body` (string, required) — reject with `422` if missing or empty
   - `title` (string, optional)
   - `group` (string, optional)
   - `priority` (integer 1–5, optional; default 3)
   - `tags` (array of strings, optional; default `[]`)
   - `url` (string, optional; must be a valid URL if provided)
   - `extras` (object with string values, optional; default `{}`)
   - reject unknown top-level keys with `422`
5) Persist message with structured fields + request metadata (headers redacted, query params captured)
6) Evaluate enabled rules for that user
7) For each matching rule:
   - create a delivery row `status=queued`, `next_attempt_at=now`
8) Return `201` with `{ "message_id": "..." }`

## Rule evaluation model

Rule filters can constrain:

- `ingest_endpoint_id` (optional) — message must come from one of the listed endpoints
- `body` (optional): contains substrings or regex match against `body` field
- `priority` (optional): min/max range (e.g., only priority ≥ 4)
- `tags` (optional): message must have at least one of the listed tags (any-of match)
- `group` (optional): exact match on `group` field

Matching behavior:

- If a filter field is omitted, it does not restrict matching.
- A rule matches if all provided conditions match (AND across filter dimensions).

## Delivery model

Deliveries are handled asynchronously by the worker.

### Worker loop

- Repeatedly:
  1) Select due deliveries:
     - `status in ('queued','retry') AND next_attempt_at <= now()`
     - lock rows using Postgres row locks to avoid double-send (e.g., `SELECT ... FOR UPDATE SKIP LOCKED`)
  2) Mark selected rows `status='sending'`
  3) For each delivery:
      - Build provider request from:
        - channel config
        - rule `payload_template_json` rendered against the message
      - Send via provider:
        - Bark: HTTP `POST {server_base_url}/push`
        - ntfy: HTTP `POST {server_base_url}/{topic}`
        - MQTT: publish to `{broker_host}:{broker_port}` on `topic`
      - On success: `status='sent'`, set `sent_at`
      - On failure:
       - increment `attempt_count`
       - set `status='retry'` if attempts remaining else `status='failed'`
       - set `next_attempt_at = now + backoff(attempt_count)`
       - save `last_error`

### Exponential backoff

Proposed:

- `delay_seconds = min(max_delay, base_delay * (2 ** (attempt_count - 1)))`
- add small random jitter (optional)
- defaults:
  - base_delay = 5s
  - max_delay = 30m
  - max_attempts = 10

## Extensibility (future channels)

Keep “channel providers” as a small abstraction:

- `ChannelProvider.validate_config(config) -> errors`
- `ChannelProvider.send(message, rendered_payload, config) -> (ok, response_meta)`

Core forwarding remains the same; adding a new channel means:

- new provider implementation
- UI form additions
- config validation
