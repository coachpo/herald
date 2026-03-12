# Product Scope

## Summary

Herald lets a single user ingest structured JSON messages, store them, inspect them in a web dashboard, and forward matching messages to notification channels.

## Primary Jobs

- Accept machine-generated events over HTTP without requiring a full webhook provider integration
- Preserve the incoming message plus request metadata for later inspection
- Route matching messages to Bark, ntfy, or MQTT with user-controlled templates
- Offer a lightweight dashboard for setup, triage, and cleanup

## Current User-Facing Features

### Account and auth

- Email/password signup
- Email verification flow
- Login + refresh-token rotation
- Forgot/reset password
- Change email
- Change password
- Delete account

### Ingest

- Multiple ingest endpoints per user
- Header-authenticated ingest via `X-Herald-Ingest-Key`
- Structured JSON payloads with:
  - `body` required
  - optional `title`, `group`, `priority`, `tags`, `url`, `extras`
- 1 MB payload limit
- JSON-only requests

### Messages

- Message list with filters for endpoint, search text, group, priority, tag, and time range
- Message detail showing body, structured fields, extras, headers, query params, and delivery history
- Soft delete for individual messages
- Batch delete for messages older than N days

### Channels

- Bark channels with `server_base_url`, `device_key`/`device_keys`, and default Bark payload JSON
- ntfy channels with server URL, topic, optional bearer/basic auth, and default headers JSON
- MQTT channels with broker, topic, auth, TLS, QoS, retain, client id, and keepalive settings
- Immediate send-test action per channel

### Rules

- Filter on ingest endpoint IDs
- Filter on body substrings or regex
- Filter on priority range
- Filter on tags (any match)
- Filter on exact group value
- Target exactly one channel per rule
- Payload templates using `{{message.*}}`, `{{request.*}}`, and `{{ingest_endpoint.*}}`
- No-send rule test endpoints and UI preview

### Edge lite

- Optional Cloudflare Worker mode for Bark/ntfy HTTP fanout from a KV snapshot
- Best-effort only; no MQTT, durable retries, or stored history at the edge

## Intended Users

- Developers wiring scripts, CI jobs, home automation, or cron jobs into notifications
- Operators who want lightweight self-hosted forwarding instead of a full alerting stack
- Individuals who want per-source ingest endpoints and searchable message history

## Non-Goals

- Multi-tenant organizations, teams, or RBAC
- Exactly-once delivery guarantees
- Message editing after ingest
- Attachment/file upload handling
- Complex rule DSLs beyond the current filter dimensions
- Durable queue semantics in the edge package

## Product Constraints

- Unverified users can log in, but write actions are gated and ingest may be blocked depending on settings
- Dashboard auth is browser-to-backend JWT, not server-side session auth
- SQLite is the default runtime storage in this repo
- Edge-lite is intentionally narrower and less safe than the backend worker

## Success Criteria

- A user can sign up, verify email, create an endpoint, ingest a JSON payload, and see the stored message
- A user can create a channel and rule, ingest a matching message, and see delivery attempts recorded
- A user can inspect stored metadata without secrets leaking through headers or UI rendering
- A user can clean up old messages without hard-deleting the whole account
