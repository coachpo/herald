# API Guide

`docs/openapi.yaml` is generated from the FastAPI app and is the schema reference.

## Auth

Dashboard APIs use `Authorization: Bearer <access token>`. Refresh tokens are sent in JSON to `/api/auth/refresh`; the frontend stores them in `sessionStorage`.

Endpoints:

- `POST /api/auth/signup`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/change-email`
- `POST /api/auth/change-password`
- `POST /api/auth/delete-account`

Password recovery is an operator CLI action: `herald-backend reset-password <email>`.

## Ingest

```http
POST /api/ingest/{endpoint_id}
Content-Type: application/json
X-Herald-Ingest-Key: <raw key>
```

Allowed fields: `body` (required), `title`, `group`, `priority`, `tags`, `url`, `extras`.

Relay headers:

- `X-Herald-Message-Id`
- `X-Herald-Received-At`
- `X-Herald-Relay-Via`

Responses:

- `201 {"message_id":"..."}` for a new message.
- `200 {"message_id":"...","duplicate":true}` for a replayed relay id.
- `400`, `401`, `403`, `413`, `415`, or `422` for invalid requests.

## Dashboard Resources

Ingest endpoints:

- `GET /api/ingest-endpoints`
- `POST /api/ingest-endpoints`
- `GET /api/ingest-endpoints/{endpoint_id}`
- `PATCH /api/ingest-endpoints/{endpoint_id}`
- `POST /api/ingest-endpoints/{endpoint_id}/revoke`
- `DELETE /api/ingest-endpoints/{endpoint_id}`

Messages:

- `GET /api/messages`
- `GET /api/messages/{message_id}`
- `DELETE /api/messages/{message_id}`
- `POST /api/messages/batch-delete`
- `GET /api/messages/{message_id}/deliveries`

Channels:

- `GET /api/channels`
- `POST /api/channels`
- `DELETE /api/channels/{channel_id}`
- `POST /api/channels/{channel_id}/test`

Rules:

- `GET /api/rules`
- `POST /api/rules`
- `GET /api/rules/{rule_id}`
- `PATCH /api/rules/{rule_id}`
- `DELETE /api/rules/{rule_id}`
- `POST /api/rules/test`
- `POST /api/rules/{rule_id}/test`

## Edge Config

`GET /api/edge-config` requires `Authorization: Bearer $EDGE_SYNC_TOKEN`. It returns active endpoint ids and `key_sha256` values only.
