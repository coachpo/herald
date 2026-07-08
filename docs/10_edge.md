# Edge Relay

The `edge/` package contains two store-and-forward relays. Cloudflare is the upstream for international senders and forwards to the backend. EdgeOne is the China entry point and forwards to Cloudflare.

```text
Sender -> EdgeOne Pages KV -> Cloudflare Worker Durable Object -> Backend -> providers
Sender -> Cloudflare Worker Durable Object -> Backend -> providers
```

The backend remains the only rule engine and provider delivery engine.

## Public Ingest

All entry points accept the same request:

```http
POST /api/ingest/{endpoint_id}
Content-Type: application/json
X-Herald-Ingest-Key: <raw key>
```

Allowed JSON fields are `body`, `title`, `group`, `priority`, `tags`, `url`, and `extras`. The body limit is 1 MiB.

Relays return `202 {"message_id":"...","status":"relayed"}` after the envelope is durably stored. The backend returns `201 {"message_id":"..."}` for a new message and `200 {"message_id":"...","duplicate":true}` for a repeated relay id.

## Relay Headers

Relays preserve the raw body and append:

- `X-Herald-Message-Id`: UUID minted by the first relay
- `X-Herald-Received-At`: ISO timestamp minted by the first relay
- `X-Herald-Relay-Via`: `edgeone`, `cloudflare`, or `edgeone,cloudflare`

The backend only trusts these headers after normal ingest-key authentication.

## Config

The backend exports endpoint digests from `GET /api/edge-config` with `Authorization: Bearer $EDGE_SYNC_TOKEN`.

```json
{
  "version": "sha-prefix",
  "updated_at": "2026-07-08T00:00:00Z",
  "ingest_endpoints": [
    { "id": "uuid", "key_sha256": "hex" }
  ]
}
```

Relays cache config for 60 seconds. Push config to both relays with:

```bash
EDGE_SYNC_TOKEN="$EDGE_SYNC_TOKEN" RELAY_ADMIN_TOKEN="$RELAY_ADMIN_TOKEN" \
  python3 scripts/sync_edge_config.py \
    --backend https://backend.example.com \
    --edges https://cf.example.workers.dev,https://edge.example.cn
```

## Admin Endpoints

Both relays expose:

- `GET /healthz`
- `POST /admin/config`
- `GET /admin/status`
- `POST /relay/drain`

Admin endpoints require `Authorization: Bearer $RELAY_ADMIN_TOKEN`. `/admin/status` returns pending count, dead count, oldest pending timestamp, and config version. `/relay/drain` returns drained, failed, and dead counts.

Permanent upstream statuses are `400`, `401`, `403`, `404`, `413`, `415`, and `422`. Other failures retry with exponential backoff. Pending envelopes older than 7 days move to dead records; dead records are retained for about 30 days.

## Cloudflare

- Entry: `edge/cloudflare/src/worker.mjs`
- Config: `edge/cloudflare/wrangler.toml`
- Buffer: Durable Object SQLite binding `RELAY_BUFFER`
- KV: `EDGE_CONFIG` stores only the config object
- Retry: Durable Object alarm with exponential backoff
- Drain batch: up to 25 pending rows

`wrangler.toml` must be updated before deploy:

- Set `[vars].UPSTREAM_URL` to the backend base URL.
- Replace `REPLACE_WITH_NAMESPACE_ID` with the Cloudflare KV namespace id for `EDGE_CONFIG`.
- Keep the `RelayBuffer` Durable Object binding and `new_sqlite_classes = ["RelayBuffer"]` migration.
- Set `RELAY_ADMIN_TOKEN` as a Worker secret.

Commands from `edge/`:

```bash
npm install
npm test
npm run lint
npm run dev
npm run deploy
```

## EdgeOne

- Entry: `edge/edgeone/edge-functions/[[default]].js`
- Build helper: `edge/edgeone/build.sh`
- Buffer: Pages KV keys prefixed with `p_`
- Dead records: Pages KV keys prefixed with `d_`
- Retry: opportunistic drain plus GitHub Actions fallback
- Drain batch: 20 pending keys

EdgeOne Pages injects the KV binding as global `EDGE_CONFIG`, not `context.env.EDGE_CONFIG`. `context.env` must provide `UPSTREAM_URL` and `RELAY_ADMIN_TOKEN`.

Provisioning requirements:

- Create or link the EdgeOne Pages project.
- In the EdgeOne Pages console, create a Pages KV namespace and bind it to the project with binding name `EDGE_CONFIG`. EdgeOne injects this as a global variable, not on `context.env`.
- Set `UPSTREAM_URL` to the Cloudflare Worker base URL.
- Set `RELAY_ADMIN_TOKEN` as an EdgeOne environment variable.
- Deploy the function, then run `scripts/sync_edge_config.py` so `/admin/config` writes the active endpoint digest config.

Deploy from `edge/edgeone/`:

```bash
bash build.sh
npx edgeone pages link
npx edgeone pages deploy
```

China mainland service requires an ICP-filed domain. Without that, use a non-mainland EdgeOne zone.

## Drain Fallback

`.github/workflows/edge-drain.yml` calls the EdgeOne `/relay/drain` endpoint every five minutes. Configure repository secrets:

- `EDGEONE_DRAIN_URL`: full EdgeOne drain URL including `/relay/drain`, for example `https://edge.example.cn/relay/drain`
- `RELAY_ADMIN_TOKEN`
