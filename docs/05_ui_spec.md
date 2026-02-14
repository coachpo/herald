# UI spec — Beacon Spear v0.1

## Tech (decision)

- Framework: **Next.js (latest stable)** using the **App Router**
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
  - Create Bark channel
  - Create rule
- Recent messages table:
  - time, endpoint, payload preview, delivery status summary
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

### Messages list

- Filters:
  - endpoint dropdown
  - search box (substring on payload_text)
  - time range
- Table columns:
  - received_at
  - endpoint
  - payload preview
  - deliveries summary (sent/failed/pending)
- Batch delete:
  - “delete messages older than N days”
  - optional endpoint scope

### Message detail

- Raw payload viewer (monospace, wrap toggle)
- Metadata:
  - content type, remote ip, user agent
  - query params JSON
  - headers JSON (redacted)
- Deliveries list:
  - each rule + channel
  - status, attempts, next attempt, last error, response meta

### Channels (Bark)

#### Channel list

- name, server base URL, disabled/enabled

#### Channel create/edit

- Fields:
  - name
  - server_base_url
  - device_key (or device_keys list, optional)
  - default Bark payload fields (two modes):
    - Form mode for common Bark v2 fields (exact key names)
    - JSON mode for full Bark payload object

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
  - payload contains (one per line; optional)
  - payload regex (optional)
- Target channel:
  - select one Bark channel
- Bark request payload:
  - form mode (common Bark v2 fields)
  - JSON mode (full payload object)
  - template helper showing available variables

#### Rule test

- Input:
  - choose ingest endpoint
  - sample payload text
- Output:
  - “matches: yes/no”
  - rendered Bark JSON payload preview (not sent)

## UI constraints / guardrails

- Block create actions if email not verified; show banner prompting verification.
- Warn when regex is invalid.
- Warn when Bark JSON is not valid JSON.

## Account page

- Profile
  - email (show verified/unverified)
  - “resend verification email” if unverified
- Change email (requires re-verification)
- Change password
