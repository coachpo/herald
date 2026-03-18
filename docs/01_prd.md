# Product Scope

## Summary

Herald lets a single user ingest structured JSON messages, store them, inspect them in a web dashboard, and forward matching messages to notification channels.

## Primary Jobs

- Accept machine-generated events over HTTP without requiring a full webhook provider integration.
- Preserve the incoming message plus request metadata for later inspection.
- Route matching messages to Bark, ntfy, MQTT, or Gotify with user-controlled templates.
- Offer a lightweight dashboard for setup, triage, and cleanup.

## Current User-Facing Features

### Account and auth

- Email/password signup, login, logout, and refresh-token rotation.
- Account page for resend verification, change email, change password, and delete account.
- Verify-email and reset-password token submission endpoints plus matching frontend pages.
- Resend-verification and forgot-password requests create hashed tokens server-side, but this repo does not implement outbound email delivery.

### Ingest

- Multiple ingest endpoints per user.
- Header-authenticated ingest via `X-Herald-Ingest-Key`.
- Structured JSON payloads with:
  - `body` required
  - optional `title`, `group`, `priority`, `tags`, `url`, `extras`
- 1 MB payload limit.
- JSON-only requests.

### Messages

- Message list with the currently implemented backend filters for endpoint, priority range, and time range.
- Message detail showing body, structured fields, extras, headers, query params, and delivery history.
- Soft delete for individual messages.
- Batch delete for messages older than N days, optionally scoped to one ingest endpoint.
- The dashboard currently renders extra search/group/tag controls, but the backend does not honor them yet.

### Channels

- Bark channels with `server_base_url`, `device_key`/`device_keys`, and default Bark payload JSON.
- ntfy channels with server URL, topic, optional bearer/basic auth, and default headers JSON.
- MQTT channels with broker, topic, auth, TLS, QoS, retain, client id, and keepalive settings.
- Gotify channels with server URL, application token, optional priority, extras, and payload defaults.
- Immediate send-test action per channel.

### Rules

- Filter on ingest endpoint IDs.
- Filter on body substrings or regex.
- Filter on priority range.
- Filter on tags (any match).
- Filter on exact group value.
- Target exactly one channel per rule.
- Payload templates using `{{message.*}}`, `{{request.*}}`, and `{{ingest_endpoint.*}}`.
- No-send rule test endpoints and UI preview.

### Edge lite

- Optional Cloudflare Worker mode for Bark/ntfy HTTP fanout from a KV snapshot.
- Best-effort only; no MQTT, durable retries, or stored history at the edge.

## Intended Users

- Developers wiring scripts, CI jobs, home automation, or cron jobs into notifications.
- Operators who want lightweight self-hosted forwarding instead of a full alerting stack.
- Individuals who want per-source ingest endpoints and searchable message history.

## Non-Goals

- Multi-tenant organizations, teams, or RBAC.
- Exactly-once delivery guarantees.
- Message editing after ingest.
- Attachment/file upload handling.
- Complex rule DSLs beyond the current filter dimensions.
- Durable queue semantics in the edge package.
- Built-in outbound email delivery for verification or password-reset tokens.

## Product Constraints

- Unverified users can log in and read.
- The shipped frontend disables common mutating dashboard flows until `email_verified_at` is set.
- Backend ingest is blocked until `email_verified_at` is set.
- Dashboard auth is browser-to-backend JWT, not server-side session auth.
- PostgreSQL is the production and supported backend database.
- Edge-lite is intentionally narrower and less safe than the backend worker.

## Success Criteria

- A user can sign up, submit a valid verification token, create an endpoint, ingest a JSON payload, and see the stored message.
- A user can create a channel and rule, ingest a matching message, and see delivery attempts recorded.
- A user can inspect stored metadata without secrets leaking through headers or UI rendering.
- A user can clean up old messages without hard-deleting the whole account.
