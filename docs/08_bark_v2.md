# Bark API v2 integration notes

This document describes the Bark provider (Bark API v2).

## Endpoint pattern

- Push endpoint: `POST {server_base_url}/push`
- Health endpoints (optional for diagnostics):
  - `GET {server_base_url}/ping`
  - `GET {server_base_url}/healthz`
  - `GET {server_base_url}/info`

`server_base_url` must be configurable per channel so users can target any Bark server (cloud or self-hosted).

## Request payload (JSON)

Bark v2 expects a JSON object with specific key names. Some “boolean” flags are represented as the string `"1"` instead of a JSON boolean.

Beacon Spear design:

- **Channel** stores `server_base_url` and `device_key` (or `device_keys`) as secrets.
- **Rule** stores the rest of the Bark payload as a template.
- Worker renders template → merges channel defaults → injects `device_key(s)` → `POST /push`.

### Common fields (per Bark v2)

Required:

- `device_key` (string) — device key (or use `device_keys`)
- `body` (string) — main content

Optional:

- `device_keys` (array of strings) — batch push
- `title` (string)
- `subtitle` (string)
- `level` (string) — one of: `critical`, `active`, `timeSensitive`, `passive`
- `volume` (string) — `0` to `1` (string form)
- `badge` (number) — badge count
- `call` (string) — must be `"1"` to repeat sound
- `autoCopy` (string) — must be `"1"` to auto copy
- `copy` (string) — text to copy
- `sound` (string) — sound name
- `icon` (string) — icon URL
- `group` (string) — group identifier
- `ciphertext` (string) — base64; encrypted payload mode
- `isArchive` (string) — must be `"1"` to archive
- `url` (string) — URL to open
- `action` (string) — if set to `"none"`, tap does nothing

## UI requirements (“mirror Bark fields”)

Channel form must show:

- `server_base_url`
- `device_key` (and optionally `device_keys`)
- a JSON editor for `default_payload_json` (sent with every push)

Rule form must show a “Bark payload” editor that uses **the same field names** as Bark v2.

Because `device_key(s)` are secrets and stored on the channel, the rule editor should:

- either hide `device_key(s)` fields, or
- show them as read-only values sourced from the selected channel

Additionally, provide a **raw JSON mode** that allows users to enter arbitrary keys so the UI stays compatible if Bark adds new fields.

## Response handling

Worker should record:

- HTTP status code
- a small response body snippet (size-capped)
- any parsed JSON response fields (if present)

This metadata is shown in the message’s delivery history.
