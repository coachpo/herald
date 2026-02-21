# UI spec — Beacon Spear v1.0

> **Breaking upgrade from v0.2.** See `01_prd.md § Breaking changes from v0.2`.

## Tech (decision)

- Framework: **React 19 + Vite** with **React Router**
- Language: TypeScript
- Styling: Tailwind CSS
- UI components: shadcn/ui (or equivalent lightweight component set)
- Auth: JWT (access token) for API calls
- Data access: browser `fetch` to backend `/api/*`
  - include `Authorization: Bearer <access_token>` for authenticated calls
  - on app load (and on 401), call `/api/auth/refresh` to obtain a new access token

## Navigation (top-level)

- Dashboard
- Messages
- Ingest endpoints
- Channels
- Rules
- Account (profile, change password)

## Theme

- Theme toggle cycles: `System → Light → Dark`.
- Persistence: `localStorage` key `beacon_theme`.
- Implementation: `<html data-theme="light|dark">` when set; unset for System.

## Pages

### Auth

- Sign up
  - email + password
  - confirmation message “check your email”
- Verify email
  - success/failure states
- Login
- Forgot password
- Reset password
- Resend verification
  - if user is unverified, show “resend verification email” action (rate limited)

### Dashboard

- Quick actions:
  - Create ingest endpoint
  - Create channel
  - Create rule
- Recent messages table:
  - time, endpoint, title (or body preview), priority badge, tags, group, delivery status summary
- Recent delivery failures panel (if any)

### Ingest endpoints

- List endpoints with:
  - name, created, last used, status (active/revoked)
  - ingest URL (copy)
- Create endpoint:
  - name
  - after create: show token once + show full URL once + “copy”
- Revoke endpoint:
  - confirmation modal

- Archive endpoint:
  - hides the endpoint from the list (does not delete message history)
  - archiving also revokes the endpoint

### Messages list

- Filters:
  - endpoint dropdown
  - search box (substring on body)
  - group dropdown/text
  - priority range (min/max)
  - tag filter (multi-select or text)
  - time range
- Table columns:
  - received_at
  - endpoint
  - title (or body preview if no title)
  - priority (badge with color coding: 1=gray, 2=blue, 3=default, 4=orange, 5=red)
  - tags (chips)
  - group
  - deliveries summary (sent/failed/pending)
- Batch delete:
  - "delete messages older than N days"
  - optional endpoint scope

### Message detail

- Structured fields (prominent display):
  - title
  - body (monospace, wrap toggle)
  - priority (badge)
  - tags (chips)
  - group
  - url (clickable link)
- Extras section (collapsible):
  - key-value table of all extras
- Request metadata (collapsible):
  - content type, remote ip, user agent
  - query params JSON
  - headers JSON (redacted)
- Deliveries list:
  - each rule + channel
  - status, attempts, next attempt, last error, response meta

### Channels (bark/ntfy/mqtt)

#### Channel list

- name, server base URL, disabled/enabled

#### Channel create/edit

- Fields (type-specific):
  - `bark`:
    - name
    - server_base_url
    - device_key (or device_keys list, optional)
    - default payload JSON (arbitrary Bark v2 fields)
  - `ntfy`:
    - name
    - server_base_url
    - topic
    - optional auth: bearer token OR basic user/pass
    - default headers JSON
  - `mqtt`:
    - name
    - broker_host / broker_port
    - topic
    - optional auth: username/password
    - optional TLS + insecure
    - qos/retain/client_id/keepalive_seconds

Notes:

- “Form mode” and “JSON mode” must round-trip without changing keys.
- JSON mode must allow arbitrary keys to preserve Bark parity.

### Rules

#### Rule list

- name, enabled, endpoint filter summary, text filter summary, channel target

#### Rule create/edit

- name + enabled
- Filters:
  - ingest endpoints multiselect (optional)
  - body contains (one per line; optional)
  - body regex (optional)
  - priority range: min/max dropdowns (optional)
  - tags filter: multi-select or comma-separated text (any-of match; optional)
  - group: exact match text input (optional)
- Target channel:
  - select one channel
- Payload template (JSON):
  - single JSON editor; label reflects selected channel type (Bark/ntfy/MQTT)
  - template variable reference panel showing all available variables:
    - **Message fields**: `{{message.title}}`, `{{message.body}}`, `{{message.group}}`, `{{message.priority}}`, `{{message.tags}}`, `{{message.url}}`, `{{message.id}}`, `{{message.received_at}}`
    - **Message extras**: `{{message.extras.<key>}}` (with note: key names depend on what the sender includes)
    - **Request metadata**: `{{request.content_type}}`, `{{request.remote_ip}}`, `{{request.user_agent}}`, `{{request.headers.<name>}}`, `{{request.query.<name>}}`
    - **Ingest endpoint**: `{{ingest_endpoint.id}}`, `{{ingest_endpoint.name}}`

#### Rule test

- Input:
  - choose ingest endpoint
  - sample JSON payload (structured: title, body, group, priority, tags, url, extras)
- Output:
  - list of matching rules (the rules that would trigger for that sample)
  - for each match: channel type + rendered payload preview (not sent)

## UI constraints / guardrails

- Block create actions if email not verified; show banner prompting verification.
- Warn when regex is invalid.
- Warn when payload template JSON is not valid JSON.
- Validate priority range (1–5) in rule filter inputs.
- Show inline validation for the sample JSON payload in rule test (must be valid JSON with `body` field).

## Account page

- Profile
  - email (show verified/unverified)
  - “resend verification email” if unverified
- Change email (requires re-verification)
- Change password
