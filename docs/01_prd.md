# Product Scope

Herald is a self-hosted notification gateway for one operator or a small trusted group. It receives structured JSON events, keeps filterable history, and forwards matched events to notification providers.

## User Jobs

- Create per-source ingest endpoints and copy a stable URL plus raw key.
- Send machine-generated JSON to Herald from scripts, CI, automation, or services.
- Inspect received messages, request metadata, and delivery attempts.
- Define channels and rules for Bark, ntfy, MQTT, and Gotify.
- Use Cloudflare and EdgeOne relays when direct network paths are unreliable.

## Current Features

- Signup, login, token refresh, logout, change email, change password, delete account.
- CLI password reset with `herald-backend reset-password <email>`.
- JSON ingest with required non-empty `body` and optional `title`, `group`, `priority` 1-5, string-array `tags`, http(s) `url`, and string-valued `extras`.
- Message list/detail, delivery history, soft delete, and age-based batch delete optionally scoped to one endpoint.
- Channel create/list/delete/test for Bark, ntfy, MQTT, and Gotify.
- Rule create/list/get/update/delete/test APIs with payload templates. Live delivery matching applies body, priority, and group filters; the UI and preview APIs also store/test endpoint-id and tag filters.
- Cloudflare Durable Object relay and EdgeOne Pages KV relay.

## Non-Goals

- Team/RBAC administration.
- Built-in email delivery.
- File attachments.
- Provider-level exactly-once delivery.
- Edge-side rule evaluation or provider dispatch.
