# Security & privacy — Beacon Spear v0.2

This app has two primary attack surfaces:

- public ingest endpoints (token in URL)
- self-signup and email flows

## Authentication & sessions

- Dashboard API auth uses **JWT access tokens**:
  - client sends `Authorization: Bearer <access_token>` on authenticated `/api/*` requests
  - access tokens are short-lived
- Session continuity uses a **refresh token** stored server-side (hashed) and delivered to the browser as an `HttpOnly; Secure; SameSite=Strict` cookie.
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

## Ingest token security

- Ingest endpoint token is a long random secret (>= 32 bytes).
- Store only a hash of the token.
- Token is displayed only once at creation time.
- Revoked tokens are rejected.

## Payload handling

- Accept arbitrary UTF‑8 text.
- Reject > 1MB payloads with HTTP `413`.
- Reject invalid UTF‑8 with HTTP `400`.
- Never attempt to parse/execute payload content.

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
