# API

All send bodies use `Content-Type: application/json`. `Authorization: Bearer <token>` is required: the ingest token is accepted only by `/api/ingest`, and the independent admin token protects management routes. `/health` is public. Tokens are compared using constant-time digest comparisons.

## Receive a message

`POST /api/ingest` (ingest token) and `POST /api/messages` (admin token) use the same durable receipt operation:

```json
{
  "title": "Backup",
  "body": "Backup completed",
  "priority": 3,
  "target_ids": ["target-id"],
  "idempotency_key": "backup-job-123"
}
```

`body` is required and nonempty. `title` defaults to empty; `priority` is an integer from 1 to 5 and defaults to 3. `target_ids` and `idempotency_key` are optional. Unknown fields are rejected and request bodies are limited to 1 MiB. Without `target_ids`, enabled default targets are used. Explicit targets must exist and be enabled; an empty selection is rejected.

The first accepted message returns `201` after its message and all delivery jobs commit. Same key and same request return `200` with `duplicate: true`; same key and different request return `409`. Omitting the key always creates a new message. The key is part of the JSON body, not a relay header. A receipt success is not provider-delivery success.

## Management

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/session` | Verify the management token |
| GET | `/api/settings` | Read nonsecret operational settings |
| GET / POST | `/api/targets` | List/create forwarding targets |
| PUT / DELETE | `/api/targets/{id}` | Replace/delete a target, subject to outstanding-work constraints |
| GET | `/api/messages` | Paginated message list (`limit`, `before`) |
| GET | `/api/messages/{id}` | Message and per-target delivery details |
| POST | `/api/deliveries/{id}/retry` | Retry only a terminally failed delivery |
| POST | `/api/cleanup` | Apply the successful-history retention policy |

A target has `name`, `kind` (`bark`, `ntfy`, `mqtt`, `gotify`), `config`, `is_default`, and `enabled`. Configurations are encrypted at rest; secret fields are omitted in read responses. On a same-kind update, omit an unchanged secret field to preserve it. Supply a new value to replace it; changing provider kind requires complete configuration and is rejected while unfinished work exists.

| Kind | Configuration |
| --- | --- |
| Bark | `server_base_url`, `device_key` |
| ntfy | `server_base_url`, `topic`, optional `access_token` |
| Gotify | `server_base_url`, `app_token` |
| MQTT | `broker_host`, `topic`; optional `broker_port` (1883), `username`/`password` together, `tls` (false), `qos` (1), `retain` (false) |

Destinations must satisfy SSRF protection at configuration and dispatch. HTTP redirects are not followed. MQTT private destinations are also rejected. Provider failures expose sanitized categories, never credentials or complete transport exception strings.

## Delivery states

Each target progresses from `pending` to `sending`, then `sent`, delayed `retry`, or terminal `failed`. Failed retries preserve total attempts and start a new bounded attempt cycle. `sent` deliveries cannot be retried. See [Architecture](02_architecture.md) for crash/retry semantics and [generated schema](openapi.yaml) for request models.

HTTP `2xx` delivery outcomes mean provider acceptance, not end-device display. MQTT QoS 0 confirms the local publish write; QoS 1 waits for broker PUBACK and QoS 2 for the QoS exchange. None proves consumer processing. ntfy uses its JSON publisher to retain Unicode titles.
