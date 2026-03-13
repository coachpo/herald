# Security And Privacy

## Auth Model

- Dashboard APIs use bearer access tokens in the `Authorization` header.
- Refresh tokens are stored server-side as hashes and rotated on every use.
- Frontend stores refresh tokens in `sessionStorage` and access tokens in memory.
- API requests use `credentials: "omit"`; backend auth does not rely on session cookies.

## Verification Gating

- Unverified users can authenticate and read data.
- Unsafe resource methods are blocked by verified-email permission checks.
- Ingest is separately blocked when `REQUIRE_VERIFIED_EMAIL_FOR_INGEST=true`.

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

- Bark, ntfy, MQTT, and Gotify providers run SSRF checks before dispatch.
- Loopback and link-local addresses are always blocked.
- Private-network blocking is configurable per provider and enabled by default.
- Provider requests use short timeouts.

### Edge lite

- Edge-lite does not currently implement backend-style SSRF checks.
- Keep that distinction explicit in docs and threat models.

## Email Flows

- Verification emails point to `/verify-email?token=...` on `APP_BASE_URL`.
- Reset emails point to `/reset-password?token=...` on `APP_BASE_URL`.
- Email send failures are logged and treated as best-effort in the API flows.

## Edge-Lite Auth Caveat

Current edge-lite code compares `X-Herald-Ingest-Key` directly to exported `token_hash` values from the KV snapshot. It does not hash the incoming value first. Document this as implemented behavior, not as intended parity with backend ingest.

## Operational Hygiene

- Do not log secrets.
- Do not commit `.env` files or copied ingest keys.
- Keep `DJANGO_SECRET_KEY` and `JWT_SIGNING_KEY` out of source control.
- Preserve SSRF checks and channel-config encryption when editing backend code.
