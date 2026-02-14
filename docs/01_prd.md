# PRD — Beacon Spear v0.1

## Summary

Beacon Spear provides:

1) A per-user message ingestion HTTP API (token-based), where the payload is an arbitrary UTF‑8 string (no validation).
2) A web UI to manage users, ingest endpoints, messages, Bark channels, and forwarding rules.
3) A background worker that forwards messages to Bark according to rules with retries.

## Goals

- Extremely simple ingestion: accept raw text, store it, forward it.
- Web-based dashboard for non-technical usage after initial setup.
- Forwarding is “good enough”: at-least-once delivery with retries.
- Future-friendly: add more channel providers later without rewriting core ingest or storage.

## Non-goals (v0.1)

- Exactly-once delivery guarantees
- Message editing or mutation after ingest (messages are immutable; delete is allowed)
- Rich parsing/validation of payloads
- Complex rule engines (no JSONPath/CEL)
- Multi-user organizations/teams/roles

## Personas / Users

- **Single user** who wants to send themselves notifications from scripts/services.
- **Hobbyist** who wants to forward webhooks/log lines to Bark quickly.

## Key user stories

### Account and auth

- As a user, I can sign up with email+password.
- As a user, I must verify my email before I can create ingest endpoints or forward messages.
- As a user, I can request a password reset email and set a new password.
- As a user, I can resend the verification email if I didn’t receive it.
- As a user, I can change my password while logged in.
- As a user, I can change my email address (and re-verify it).

### Ingest endpoints

- As a user, I can create multiple ingest endpoints (tokens) for different sources.
- As a user, I can revoke an ingest endpoint token at any time.
- As a user, I can copy an endpoint’s ingest URL and test it with curl.

### Messages

- As a user, I can view a list of ingested messages.
- As a user, I can open a message and view:
  - raw payload text
  - `Content-Type`
  - request headers (redacted)
  - query params
  - remote IP / user-agent
  - delivery attempts/outcomes
- As a user, I can delete individual messages.
- As a user, I can batch delete messages older than N days (optionally scoped to an ingest endpoint).

### Channels (Bark)

- As a user, I can create a Bark channel that points at my Bark server (any base URL).
- As a user, I can configure Bark parameters in the UI using the same field names as Bark’s API v2.

### Forwarding rules

- As a user, I can create a forwarding rule:
  - filter by ingest endpoint (optional)
  - filter by payload_text (contains / regex; optional)
  - choose a single Bark channel as the target
  - define Bark payload fields (title/body/etc) using templates
- As a user, I can enable/disable a rule.
- As a user, I can test a rule against a sample message in the UI.
- As a user, all matching rules run; duplicates are allowed.

## Functional requirements

### Ingest

- Endpoint: `POST /api/ingest/{token}`
- Payload: request body decoded as UTF‑8 string
- Max payload: 1MB; reject larger payload with HTTP `413 Payload Too Large`
- No payload validation; store as-is
- Store request metadata:
  - Content-Type
  - query params
  - remote IP
  - user agent
  - headers (with sensitive values redacted)
- Ingest must be authenticated by the token in the URL.

### Storage

- All ingested messages must be stored in the database.
- Data is retained indefinitely until user deletion.
- Batch delete (“older than N days”) must be supported.

### Forwarding

- At-least-once delivery is acceptable.
- Retries: exponential backoff, with max attempts configurable.
- Forwarding is performed asynchronously by a worker process.

### Account management

- Self-signup (email+password) is enabled.
- Email verification is required before enabling ingest/forwarding features.
- Password reset via email is supported.
- User can:
  - change password
  - change email (requires re-verification)
  - resend verification email

## UX requirements (high level)

- Fast paths: “Create ingest endpoint” and “Create Bark channel” should be discoverable from the dashboard.
- Message detail view should show delivery attempt history clearly.
- Bark configuration should offer a “JSON mode” to mirror Bark’s payload exactly.

## Acceptance criteria (v0.1)

- A new user can sign up, verify email, create an ingest endpoint, and ingest a message successfully.
- User can create a Bark channel and a rule, ingest a message, and see a delivery attempt recorded.
- Oversize payloads are rejected and not stored.
- Sensitive headers are redacted in stored metadata and in UI.
- Batch deletion removes (soft-deletes) messages older than N days.

## Out of scope decisions to confirm before implementation

- Whether to provide global admin features (Django admin only vs additional custom pages).
- Whether deletion is soft-delete only, or also offer hard delete.
