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

`body` is required and nonempty. `title` defaults to empty; `priority` is an integer from 1 to 5 and defaults to 3. `target_ids` and `idempotency_key` are optional. Unknown fields are rejected and request bodies are limited to 1 MiB.

- A nonempty `target_ids` array selects only those targets, deduplicates IDs, and bypasses rules and defaults. An explicit `[]` is rejected.
- Omitted or `null` `target_ids` selects the union of all enabled matching rules. Only zero matching rules fall back to all enabled default targets; defaults are not added to a matched rule's targets.
- Every selected target must exist and be enabled or the whole request returns `400 target_unavailable`. An empty final selection returns `400 no_targets`. Neither case stores a partial message or any deliveries, and unavailable rule targets do not trigger fallback.

The first accepted message returns `201` after its message, routing decision, and all delivery jobs commit. Same key and same request return `200` with `duplicate: true`; same key and different request return `409`. The existing request fingerprint is unchanged: normalized request content and explicit target IDs determine it; explicit target order and duplicate IDs are equivalent. The fingerprint does not include routing revisions or calculated targets. Existing-key replay is checked before selecting targets, so changing rules, defaults, or target availability does not recalculate or add deliveries to a replayed receipt. This applies across both send endpoints. Omitting the key always creates a new message. The key is part of the JSON body, not a relay header. A receipt success is not provider-delivery success.

## Management

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/session` | Verify the management token |
| GET | `/api/settings` | Read nonsecret operational settings |
| GET / POST | `/api/targets` | List/create forwarding targets |
| PUT / DELETE | `/api/targets/{id}` | Replace/delete a target, subject to outstanding-work and rule-reference constraints |
| GET / PUT | `/api/routing` | Read/replace the complete revisioned routing configuration |
| GET | `/api/messages` | Paginated message list (`limit`, `before`) |
| GET | `/api/messages/{id}` | Message and per-target delivery details |
| POST | `/api/deliveries/{id}/retry` | Retry only a terminally failed delivery |
| POST | `/api/cleanup` | Apply the successful-history retention policy |

A target has `name`, `kind` (`bark`, `ntfy`, `mqtt`, `gotify`), `config`, `is_default`, and `enabled`. Configurations are encrypted at rest; secret fields are omitted in read responses. On a same-kind update, omit an unchanged secret field to preserve it. Supply a new value to replace it; changing provider kind requires complete configuration and is rejected while unfinished work exists.

`is_default` participates only in automatic selection when zero enabled rules match. Disabling a target excludes it from new selections but does not cancel accepted deliveries. A target referenced by any rule, including a disabled rule, cannot be deleted: `DELETE` returns `409 target_referenced_by_routing` until all references are removed. The existing unfinished-work deletion check still applies. Successfully delivered history remains available after an otherwise permitted deletion.

| Kind | Configuration |
| --- | --- |
| Bark | `server_base_url`, `device_key` |
| ntfy | `server_base_url`, `topic`, optional `access_token` |
| Gotify | `server_base_url`, `app_token` |
| MQTT | `broker_host`, `topic`; optional `broker_port` (1883), `username`/`password` together, `tls` (false), `qos` (1), `retain` (false) |

Destinations must satisfy SSRF protection at configuration and dispatch. HTTP redirects are not followed. MQTT private destinations are also rejected. Provider failures expose sanitized categories, never credentials or complete transport exception strings.

## Routing configuration

`GET /api/routing` requires the admin token and initially returns `{"revision": 0, "rules": []}`. `PUT /api/routing` also requires the admin token and `Content-Type: application/json`. Submit the revision read from the server and the complete ordered rules array, for example:

```json
{
  "revision": 0,
  "rules": [
    {
      "id": "urgent",
      "enabled": true,
      "all": [{"field": "priority", "op": "gte", "value": 4}],
      "target_ids": ["target-id"]
    }
  ]
}
```

Rule IDs are nonempty stable strings, unique within the configuration. `enabled` defaults to `true`; `all` and `target_ids` must be nonempty. The server sorts and deduplicates each target list. Conditions are flat and ANDed within a rule:

| Field | Operators | Value |
| --- | --- | --- |
| `priority` | `eq`, `gte`, `lte` | Strict integer 1–5; strings, booleans, and floats are invalid |
| `title`, `body` | `eq`, `prefix`, `contains` | String, compared as supplied with case sensitivity and no trimming |

Matching uses the normalized message defaults. Enabled rules are scanned from top to bottom; all matches contribute targets by set union without stopping or overwriting. Rule order determines configuration and matched-ID order, not target priority or send order. Unknown fields, invalid types/expressions, and duplicate rule IDs return `422`. Saving validates every target reference, including those in disabled rules; a missing target returns `400 target_unavailable`. Disabled targets may be referenced, but a matching selection of one is rejected at receipt time.

A successful replacement returns `200` with the incremented revision and normalized rules. An empty array clears rules and still increments the revision. A stale revision returns `409 routing_changed` without changing configuration. Reload before reconciling and resubmitting edits; stale clients must not overwrite a newer revision. Configuration replacement and receipt selection are serialized in SQLite write transactions.

Rules and defaults affect new receipts only; existing delivery sets are fixed. Retries and recovery do not match rules again. An attempt reads the target's latest configuration at claim time, so destination configuration is not a snapshot. Explicit target selection can bypass routing; rules are not a mandatory archival policy.

## Recorded routing decisions

Message list and detail responses add nullable `routing_decision` without changing pagination or delivery fields. For example:

```json
{
  "mode": "rules",
  "rules_revision": 1,
  "matched_rule_ids": ["urgent"]
}
```

`mode` is `explicit`, `rules`, or `defaults`. Explicit selection records a null `rules_revision` and an empty matched list. Automatic selection records the configuration revision used; default fallback records an empty matched list. Pre-upgrade messages have `routing_decision: null`; their original selection method is not inferred. Decisions contain only mode, revision, and matched IDs, not complete historical rules or target configurations, and are not used to recalculate deliveries. Use the persisted delivery records for actual targets and outcomes. The receipt body itself is unchanged.

## Delivery states

Each target progresses from `pending` to `sending`, then `sent`, delayed `retry`, or terminal `failed`. Failed retries preserve total attempts and start a new bounded attempt cycle. `sent` deliveries cannot be retried. See [Architecture](02_architecture.md) for crash/retry semantics and [generated schema](openapi.yaml) for request models.

HTTP `2xx` delivery outcomes mean provider acceptance, not end-device display. MQTT QoS 0 confirms the local publish write; QoS 1 waits for broker PUBACK and QoS 2 for the QoS exchange. None proves consumer processing. ntfy uses its JSON publisher to retain Unicode titles.
