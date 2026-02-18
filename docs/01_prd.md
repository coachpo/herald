# PRD — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** No backward compatibility with the v0.2 ingest API or message schema.

## Summary

Beacon Spear provides:

1) A per-user message ingestion HTTP API that accepts **structured JSON payloads** with rich metadata (title, body, priority, tags, group, URL, and arbitrary extras).
2) A web UI to manage users, ingest endpoints, messages, channels (Bark, ntfy, MQTT), and forwarding rules with a comprehensive template variable system.
3) A background worker that forwards messages to channels according to rules with retries.

## Goals

- Structured ingestion: accept JSON payloads with well-defined fields that map naturally to downstream notification providers (Bark, ntfy, MQTT).
- Rich template rendering: forwarding rules can reference any ingested field — title, body, priority, tags, group, URL, extras, and request metadata — in payload templates.
- Web-based dashboard for non-technical usage after initial setup.
- Forwarding is "good enough": at-least-once delivery with retries.
- Future-friendly: add more channel providers later without rewriting core ingest or storage.

## Non-goals (v1.0)

- Exactly-once delivery guarantees
- Message editing or mutation after ingest (messages are immutable; delete is allowed)
- Complex rule engines (no JSONPath/CEL)
- Multi-user organizations/teams/roles
- File/image attachment uploads (URLs only)
- Batch ingestion (multiple messages in one request)

## Breaking changes from v0.2

- Ingest API now requires `Content-Type: application/json` with a structured JSON body. Raw text bodies are no longer accepted.
- The `payload_text` field is removed. Messages now have `title`, `body`, `group`, `priority`, `tags`, `url`, and `extras` fields.
- Template variables are restructured: `{{message.payload_text}}` is removed; use `{{message.body}}`, `{{message.title}}`, etc.
- Rule text filters now operate on `body` (not `payload_text`), and new filter dimensions are available (priority, tags, group).
- The `bark_payload_template_json` legacy field on forwarding rules is removed. Use `payload_template_json` only.

## Personas / Users

- **Single user** who wants to send themselves notifications from scripts/services.
- **Hobbyist** who wants to forward webhooks/log lines to their phone quickly.
- **Developer** who wants structured alerting from CI/CD pipelines, monitoring tools, or home automation.

## Key user stories

### Account and auth

- As a user, I can sign up with email+password.
- As a user, I must verify my email before I can create ingest endpoints or forward messages.
- As a user, I can request a password reset email and set a new password.
- As a user, I can resend the verification email if I didn't receive it.
- As a user, I can change my password while logged in.
- As a user, I can change my email address (and re-verify it).
- As a user, I can permanently delete my account.

### Ingest endpoints

- As a user, I can create multiple ingest endpoints for different sources.
- As a user, I can revoke an ingest endpoint at any time.
- As a user, I can copy an endpoint's ingest URL and test it with curl.

### Messages (ingestion)

- As a user, I can send a structured JSON payload to my ingest endpoint with fields: `title`, `body`, `group`, `priority`, `tags`, `url`, and `extras`.
- As a user, only `body` is required; all other fields are optional.
- As a user, I can include arbitrary key-value pairs in `extras` for custom data that my forwarding rules can reference.
- As a user, I receive a clear error response if my JSON payload is malformed or missing required fields.

### Messages (viewing)

- As a user, I can view a list of ingested messages showing title, body preview, priority, tags, and group.
- As a user, I can open a message and view:
  - structured fields (title, body, group, priority, tags, url)
  - extras (arbitrary key-value pairs)
  - request metadata: `Content-Type`, request headers (redacted), query params, remote IP, user-agent
  - delivery attempts/outcomes
- As a user, I can delete individual messages.
- As a user, I can batch delete messages older than N days (optionally scoped to an ingest endpoint).

### Channels

- As a user, I can create a Bark channel that points at my Bark server (any base URL).
- As a user, I can configure Bark parameters in the UI using the same field names as Bark's API v2.
- As a user, I can create an ntfy channel (server + topic) and optionally configure auth.
- As a user, I can create an MQTT channel (broker + topic) and optionally configure auth/TLS/QoS.

### Dashboard theme

- As a user, I can switch the dashboard theme between System/Light/Dark, and it persists across reloads.

### Forwarding rules

- As a user, I can create a forwarding rule:
  - filter by ingest endpoint (optional)
  - filter by body text (contains / regex; optional)
  - filter by priority (min/max range; optional)
  - filter by tags (any-of match; optional)
  - filter by group (exact match; optional)
  - choose a single channel as the target (Bark/ntfy/MQTT)
  - define provider payload fields using templates
- As a user, I can write a payload template that references any ingested field:
  - `{{message.title}}`, `{{message.body}}`, `{{message.group}}`, `{{message.priority}}`
  - `{{message.tags}}` (comma-separated string), `{{message.url}}`
  - `{{message.extras.<key>}}` for arbitrary extras
  - `{{request.remote_ip}}`, `{{request.user_agent}}`, `{{request.content_type}}`
  - `{{request.headers.<name>}}`, `{{request.query.<name>}}`
  - `{{ingest_endpoint.id}}`, `{{ingest_endpoint.name}}`
  - `{{message.id}}`, `{{message.received_at}}`
- As a user, I can enable/disable a rule.
- As a user, I can test a rule against a sample message in the UI.
- As a user, all matching rules run; duplicates are allowed.

### Forwarding rule defaults

- If a payload template omits `title` or `body`, the forwarding system uses the ingested `title` and `body` as sensible defaults (provider-specific behavior).

## Functional requirements

### Ingest

- Endpoint: `POST /api/ingest/{endpoint_id}`
- Canonical URL form uses a dashless UUID (32 hex chars); the server also accepts dashed UUIDs.
- Auth: `X-Beacon-Ingest-Key: <ingest_key>`
- Content-Type: must be `application/json`
- Payload: JSON object with the following fields:
  - `body` (string, **required**) — main notification content
  - `title` (string, optional) — notification title
  - `group` (string, optional) — grouping identifier
  - `priority` (integer 1–5, optional, default 3) — 1=lowest, 5=critical
  - `tags` (array of strings, optional) — freeform tags
  - `url` (string, optional) — URL to attach to the notification
  - `extras` (object, optional) — arbitrary string key-value pairs for custom data
- Max payload: 1MB; reject larger payload with HTTP `413 Payload Too Large`
- Reject non-JSON content types with HTTP `415 Unsupported Media Type`
- Reject malformed JSON with HTTP `400 Bad Request`
- Reject missing `body` field with HTTP `422 Unprocessable Entity`
- Store request metadata:
  - Content-Type
  - query params
  - remote IP
  - user agent
  - headers (with sensitive values redacted)

### Storage

- All ingested messages must be stored in the database with structured fields.
- Data is retained indefinitely until user deletion.
- Batch delete ("older than N days") must be supported.

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

- Fast paths: "Create ingest endpoint" and "Create channel" should be discoverable from the dashboard.
- Message detail view should show structured fields prominently, with extras and request metadata in collapsible sections.
- Message list should show title (or body preview), priority badge, tags, and group.
- Rule editor should show a template variable reference panel listing all available `{{...}}` variables.
- Bark configuration should offer a "JSON mode" to mirror Bark's payload exactly.

## Acceptance criteria (v1.0)

- A new user can sign up, verify email, create an ingest endpoint, and ingest a structured JSON message successfully.
- Ingesting a payload with only `body` succeeds; ingesting without `body` returns 422.
- Ingesting a non-JSON payload returns 415.
- User can create a Bark channel and a rule using `{{message.title}}` and `{{message.body}}` in the template, ingest a message, and see a delivery attempt recorded.
- User can create an ntfy channel and an MQTT channel, create rules for each, ingest a message, and see delivery attempts recorded.
- Template variables `{{message.extras.mykey}}`, `{{request.remote_ip}}`, `{{request.headers.x-custom}}`, and `{{request.query.source}}` render correctly.
- Rule filters on priority, tags, and group correctly match/reject messages.
- Oversize payloads are rejected and not stored.
- Sensitive headers are redacted in stored metadata and in UI.
- Batch deletion removes (soft-deletes) messages older than N days.

## Open questions

- Whether to provide global admin features (Django admin only vs additional custom pages).
- Whether deletion is soft-delete only, or also offer hard delete.

Current implementation defaults:
- user-only (no global admin features beyond Django admin)
- soft-delete only
