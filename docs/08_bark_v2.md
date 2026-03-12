# Bark Provider Notes

## Current Backend Behavior

Backend Bark delivery is implemented in `backend/core/bark.py`.

- Normal dispatch is `POST {server_base_url}/push` with JSON.
- `server_base_url` is normalized to remove trailing slashes and duplicate `/push`.
- If a POST returns `404` or `405`, backend falls back to the legacy GET URL form.

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

Herald passes through arbitrary JSON keys, so common Bark payload fields can be set in the rule template or default payload JSON, including:

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

## Test Endpoint

`POST /api/channels/{id}/test` for Bark:

- merges `default_payload_json`
- overlays optional `payload_json`
- fills in default `title` / `body` if absent
- injects configured `device_key` or `device_keys`
- returns provider metadata under `provider_response`

## Safety And Limits

- Backend applies SSRF checks to Bark destination URLs.
- Response metadata is stored as capped snippets plus parsed JSON when available.
- Do not document Bark support as edge/backend identical; the edge package has a narrower safety model.
