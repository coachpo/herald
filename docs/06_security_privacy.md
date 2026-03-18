# Security And Privacy

## Auth Model

- Dashboard APIs use bearer access tokens in the `Authorization` header.
- Refresh tokens are stored server-side as hashes and rotated on every use.
- Frontend stores refresh tokens in `sessionStorage` and access tokens in memory.
- API requests use `credentials: "omit"`; backend auth does not rely on session cookies.

## Verification Gating

- Unverified users can authenticate and read data.
- The shipped frontend blocks common mutating dashboard flows for unverified users.
- The current backend does not universally enforce verified-email checks across every dashboard write route.
- Ingest is also blocked when `email_verified_at` is null. There is no `REQUIRE_VERIFIED_EMAIL_FOR_INGEST` toggle in the current codebase.

## Token Handling

- Ingest keys are generated as random secrets and stored only as hashes.
- Verification and password-reset tokens are stored only as hashes.
- Refresh token replay invalidates the whole refresh-token family.
- Password reset and password change revoke all refresh tokens.

## Browser-Side Risks

- Treat XSS as full account takeover risk.
- Do not store auth tokens in `localStorage`.
- Do not render ingested user content as HTML.

## Ingest Safety

- Only `application/json` is accepted.
- Payloads above the configured size limit are rejected.
- Unknown top-level keys are rejected.
- `extras` must be an object of string values.
- Request metadata is stored, but secrets in headers are redacted before persistence.

## Header Redaction

Exact header names redacted by backend include:

- `Authorization`
- `Proxy-Authorization`
- `Cookie`
- `Set-Cookie`
- `X-API-Key`
- `X-Auth-Token`
- `X-CSRFToken`
- `X-CSRF-Token`

Backend also redacts header names matching patterns such as `token`, `secret`, `password`, `auth`, and `key`.

## Outbound Connection Safety

### Backend worker

- Bark, ntfy, and Gotify providers run SSRF checks before dispatch and use default private-network blocking in code.
- MQTT validates the broker host with the SSRF helper and exposes `MQTT_BLOCK_PRIVATE_NETWORKS` plus `MQTT_SOCKET_TIMEOUT_SECONDS`.
- Loopback and link-local addresses are always blocked.
- Provider timeouts default to about 5 seconds in the current code.

### Edge lite

- Edge-lite does not currently implement backend-style SSRF checks.
- Keep that distinction explicit in docs and threat models.

## Verification And Reset Request Flows

- `POST /api/auth/resend-verification` and `POST /api/auth/forgot-password` create hashed tokens in PostgreSQL and log the event.
- The current repo does not send email or expose raw verification/reset tokens.
- Verification and reset pages in the frontend therefore depend on tokens arriving from an external or out-of-band mechanism.

## Edge-Lite Auth Caveat

Current edge-lite code compares `X-Herald-Ingest-Key` directly to exported `token_hash` values from the KV snapshot. It does not hash the incoming value first. Document this as implemented behavior, not as intended parity with backend ingest.

## Operational Hygiene

- Do not log secrets.
- Do not commit `.env` files or copied ingest keys.
- Keep `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` out of source control.
- Preserve SSRF checks and channel-config encryption when editing backend code.
