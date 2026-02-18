# Security & privacy — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

This app has two primary attack surfaces:

- public ingest endpoints (`endpoint_id` in URL + `X-Beacon-Ingest-Key` header)
- self-signup and email flows

## Authentication & sessions

- Dashboard API auth uses **JWT access tokens**:
  - client sends `Authorization: Bearer <access_token>` on authenticated `/api/*` requests
  - access tokens are short-lived
- Session continuity uses a **refresh token** stored server-side (hashed) and delivered to the browser.
- Refresh tokens are rotated on every use; clients must persist the latest refresh token.
- Because refresh tokens are no longer HttpOnly cookies, the dashboard must treat **XSS as full account takeover**.
  - Recommended client storage: refresh token in `sessionStorage` (per-tab) and access token in memory only.
- Because authenticated APIs do not rely on ambient cookies for auth, **CSRF tokens are not required** for state-changing API requests.
- Password storage: strong hashing (Django defaults).

Security note:

- JWT-based APIs shift the main browser risk from CSRF to **XSS**. The dashboard must treat ingested payloads as plain text (escaped) and avoid unsafe HTML rendering.

## Email verification

- Require email verification before enabling:
  - creating endpoints/channels/rules
  - ingest and forwarding (recommended)
- Verification tokens:
  - random, single-use
  - hashed at rest
  - short expiry (e.g., 24 hours)

## Password reset

- Tokens:
  - random, single-use
  - hashed at rest
  - expiry (e.g., 1 hour)
- Rate limit reset requests per email/IP to prevent abuse.

## Ingest key security

- Ingest key is a long random secret (>= 32 bytes).
- Store only a hash of the ingest key.
- Ingest key is displayed only once at creation time.
- Revoked endpoints are rejected.

## Edge forwarders (optional)

If you deploy edge forwarders (Cloudflare Workers / Tencent EdgeOne):

- Treat edge forwarder keys as independent ingest keys.
- Each hop should have its own `X-Beacon-Ingest-Key` and its own next-hop key.
- Store hop keys as secrets in the edge provider.
- Limit hop depth to prevent routing loops.

## Payload handling

- Require `Content-Type: application/json`; reject other content types with `415`.
- Parse request body as JSON; reject malformed JSON with `400`.
- Validate structured fields:
  - `body` (string, required, non-empty)
  - `title` (string, optional)
  - `group` (string, optional)
  - `priority` (integer 1–5, optional)
  - `tags` (array of strings, optional)
  - `url` (string, optional; validate URL format)
  - `extras` (object with string values, optional)
- Reject unknown top-level keys with `422` to prevent payload confusion.
- Reject > 1MB payloads with HTTP `413`.
- Never attempt to execute payload content.
- Sanitize all string fields for display (escape HTML entities in the dashboard).

## Metadata capture & redaction

Store request metadata but redact sensitive header values.

### Redaction policy

- Store all headers, but replace values with `"[REDACTED]"` for:
  - `Authorization`
  - `Proxy-Authorization`
  - `Cookie`
  - `Set-Cookie`
  - `X-API-Key`
  - `X-Auth-Token`
  - `X-CSRFToken` / `X-CSRF-Token`
- Also redact any header whose name matches:
  - `/token/i`, `/secret/i`, `/password/i`, `/auth/i`, `/key/i` (configurable)

### Query params

- Store query params as received.
- (Optional) Apply the same redaction heuristics to query keys if desired.

## Outbound connections / SSRF (Bark/ntfy/MQTT)

Because users can configure outbound destinations (Bark server URL, ntfy server URL, MQTT broker host), outbound connections can be abused for SSRF.

Mitigations (choose per deployment posture):

- Allowlist outbound destinations (best for hardened environments)
- Block private IP ranges / localhost by default (common mitigation)
- Set short timeouts and size limits on outbound requests

Given “reliability expectations are minimal”, the app can ship with basic safeguards:

- Always block loopback + link-local ranges.
- Optionally block RFC1918 private ranges (configurable).
- Enforce short timeouts.

Configuration knobs:

- `BARK_BLOCK_PRIVATE_NETWORKS`, `BARK_REQUEST_TIMEOUT_SECONDS`
- `NTFY_BLOCK_PRIVATE_NETWORKS`, `NTFY_REQUEST_TIMEOUT_SECONDS`
- `MQTT_BLOCK_PRIVATE_NETWORKS`, `MQTT_SOCKET_TIMEOUT_SECONDS`

## Rate limiting / abuse prevention

Minimum recommended:

- Signup: per-IP rate limit
- Verification/resets: per-IP and per-email rate limit
- Ingest: per-endpoint rate limit (optional)

## Data privacy

- Payloads may contain sensitive information; provide clear UI warning.
- Provide batch delete to support user cleanup.
- Optional future: per-message “expire after” or global retention policy.
