# Security & privacy — Beacon Spear v0.1

This app has two primary attack surfaces:

- public ingest endpoints (token in URL)
- self-signup and email flows

## Authentication & sessions

- Use Django auth with session cookies.
- Enforce CSRF on all state-changing UI/API endpoints (except ingest).
- Password storage: strong hashing (Django defaults).

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

## SSRF considerations (Bark server)

Because users can configure any Bark server URL, outbound HTTP requests can be abused for SSRF.

Mitigations (choose per deployment posture):

- Allowlist outbound destinations (best for hardened environments)
- Block private IP ranges / localhost by default (common mitigation)
- Set short timeouts and size limits on outbound requests

Given “reliability expectations are minimal”, v0.1 can ship with basic safeguards:

- block `localhost`, `127.0.0.0/8`, `::1`
- block RFC1918 private ranges (optional, configurable)

## Rate limiting / abuse prevention

Minimum recommended:

- Signup: per-IP rate limit
- Verification/resets: per-IP and per-email rate limit
- Ingest: per-endpoint rate limit (optional)

## Data privacy

- Payloads may contain sensitive information; provide clear UI warning.
- Provide batch delete to support user cleanup.
- Optional future: per-message “expire after” or global retention policy.

