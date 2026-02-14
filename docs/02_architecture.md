# Architecture — Beacon Spear v0.1

## High-level components

1) **Django backend**
   - JSON APIs for the dashboard
   - Ingest endpoint: `POST /api/ingest/{token}`
   - Email sending for verification + password reset (SMTP)
   - Session-cookie auth + CSRF protection for state-changing requests

2) **Next.js dashboard (latest stable)**
   - Web UI routes under `/`
   - Calls backend JSON APIs under `/api/*`

3) **Worker process**
   - Polls DB for due deliveries
   - Sends Bark v2 HTTP requests
   - Updates delivery status, schedules retries with exponential backoff

4) **Postgres**
   - Stores users, endpoints, messages, channels, rules, deliveries
   - Acts as the job queue (deliveries table)

## Authentication model

- Dashboard: backend session cookie + CSRF (cookie-based; set/read on same origin)
- Ingest API: token in URL path; no session required; CSRF exempt

## Deployment routing (simple)

To keep auth simple, host dashboard + backend on the **same origin**:

- `/api/*` → Django backend
- everything else → Next.js

This avoids cross-origin cookie/CORS complexity and keeps Django CSRF straightforward.

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

1) Request `POST /api/ingest/{token}`
2) Identify ingest endpoint by token (constant-time compare against stored hash)
3) Enforce:
   - UTF‑8 decoding (reject invalid)
   - body size ≤ 1MB (reject > 1MB)
4) Persist message + metadata (headers redacted, query params captured)
5) Evaluate enabled rules for that user
6) For each matching rule:
   - create a delivery row `status=queued`, `next_attempt_at=now`
7) Return `200`/`201` with `message_id`

## Rule evaluation model (simple)

Rule filters can constrain:

- `ingest_endpoint_id` (optional)
- `payload_text` (optional): contains or regex

Matching behavior:

- If a filter field is omitted, it does not restrict matching.
- A rule matches if all provided conditions match.

## Delivery model

Deliveries are handled asynchronously by the worker.

### Worker loop

- Repeatedly:
  1) Select due deliveries:
     - `status in ('queued','retry') AND next_attempt_at <= now()`
     - lock rows using Postgres row locks to avoid double-send (e.g., `SELECT ... FOR UPDATE SKIP LOCKED`)
  2) Mark selected rows `status='sending'`
  3) For each delivery:
     - Build Bark v2 request JSON payload from:
       - channel config (server base URL + auth/device key)
       - rule payload template rendered against the message
     - HTTP `POST {server_base_url}/push`
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
