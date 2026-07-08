# Product Scope

Herald is a self-hosted notification gateway for one operator or a small trusted group. It receives structured JSON events, keeps searchable history, and forwards matched events to notification providers.

## User Jobs

- Create per-source ingest endpoints and copy a stable URL plus raw key.
- Send machine-generated JSON to Herald from scripts, CI, automation, or services.
- Inspect received messages, request metadata, and delivery attempts.
- Define channels and rules for Bark, ntfy, MQTT, and Gotify.
- Use Cloudflare and EdgeOne relays when direct network paths are unreliable.

## Current Features

- Signup, login, token refresh, logout, change email, change password, delete account.
- CLI password reset with `herald-backend reset-password <email>`.
- JSON ingest with required `body` and optional `title`, `group`, `priority`, `tags`, `url`, and `extras`.
- Message list/detail, soft delete, and batch delete.
- Channel create/delete/test for Bark, ntfy, MQTT, and Gotify.
- Rule create/list/delete/test with payload templates.
- Cloudflare Durable Object relay and EdgeOne Pages KV relay.

## Non-Goals

- Team/RBAC administration.
- Built-in email delivery.
- File attachments.
- Provider-level exactly-once delivery.
- Edge-side rule evaluation or provider dispatch.
