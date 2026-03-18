# Bark Provider Notes

## Current Backend Behavior

Backend Bark delivery is implemented in `backend/providers/bark.py`.

- Normal dispatch is `POST {server_base_url}/push` with JSON.
- `server_base_url` is normalized to remove trailing slashes and duplicate `/push`.
- If a POST returns `404` or `405`, backend falls back to the legacy GET URL form when the payload contains a single `device_key` plus `body`.

## Channel Config

Stored encrypted in the channel config payload:

- `server_base_url`
- `device_key` or `device_keys`
- `default_payload_json`

Notes:

- UI allows pasting a full Bark key URL and normalizes it into `server_base_url` plus `device_key`.
- Bark channel validation requires `server_base_url` and at least one of `device_key` or `device_keys`.

## Rule Payload Template

- Rules store a generic `payload_template_json`.
- For Bark, backend renders the template, merges it into `default_payload_json`, then injects `device_key` or `device_keys` from channel config.
- If no rendered `body` exists, backend falls back to `message.body`.
- If no rendered `title` exists and the message has one, backend falls back to `message.title`.

## Useful Bark Fields

Herald passes through arbitrary JSON keys, so Bark V2 fields can be set in rule templates or `default_payload_json`, including:

- `title`
- `body`
- `subtitle`
- `level`
- `volume`
- `badge`
- `call`
- `autoCopy`
- `copy`
- `sound`
- `icon`
- `group`
- `isArchive`
- `url`
- `action`
- `device_keys`
- `ciphertext`
- `iv`

## Test Endpoint

`POST /api/channels/{channel_id}/test` for Bark:

- merges `default_payload_json`
- treats optional `payload_json` as the synthetic test message input
- fills in default `title` / `body` if absent
- injects configured `device_key` or `device_keys`
- returns provider metadata under `provider_response`

## Safety And Limits

- Backend applies SSRF checks to Bark destination URLs.
- Backend uses a 5 second HTTP timeout by default.
- Response metadata is stored as capped snippets plus parsed JSON when available.
- Edge uses the same `/push` payload model, but does not implement backend SSRF checks or the legacy GET fallback.
