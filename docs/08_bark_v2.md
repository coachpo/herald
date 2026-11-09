# Bark Provider Notes

## Current Backend Behavior

Backend Bark delivery is implemented in [backend/providers/bark.py](../backend/providers/bark.py). This document describes Herald's payload construction and transport, not a guarantee that every external Bark server supports every field.

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
- If the merged payload's `body` is empty or absent, backend falls back to `message.body`.
- If the merged payload's `title` is empty or absent and the message has one, backend falls back to `message.title`.
- Live worker and rule-preview template contexts differ; see the [API guide limitations](04_api_spec.md#rules) before relying on metadata placeholders.

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
- treats optional `payload_json` as the synthetic test message input, not as an arbitrary Bark payload override; for example, an `icon` supplied there is not automatically merged into the outgoing payload
- fills in default `title` / `body` if absent
- injects configured `device_key` or `device_keys`
- performs a real provider send and returns provider metadata under `provider_response`

## Safety And Limits

- Backend applies SSRF checks to Bark destination URLs.
- Backend uses a 5 second HTTP timeout by default.
- Response metadata includes a body snippet capped at 2,048 bytes plus parsed JSON when available; the parsed JSON is not size-capped by this helper.
- Edge relays do not dispatch Bark notifications; they only buffer and forward ingest requests to the backend.
