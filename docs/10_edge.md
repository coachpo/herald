# Edge Relay

The `edge/` package contains two store-and-forward relays. The intended routing uses Cloudflare as the international entry point forwarding to the backend, and EdgeOne as the China entry point forwarding to Cloudflare. This is a configurable topology, not evidence of an actual deployment or regional availability; operators set each relay's `UPSTREAM_URL`.

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

Relays return `202 {"message_id":"...","status":"relayed"}` after the buffer write completes, not after backend ingestion or provider delivery. A successful next-hop HTTP response removes that hop's pending record. The backend returns `201 {"message_id":"..."}` for a new message and `200 {"message_id":"...","duplicate":true}` for a repeated relay id.

## Relay Headers

Relays preserve the raw body and append or forward relay metadata:

- `X-Herald-Message-Id`: valid incoming UUID, or a UUID minted when absent or invalid
- `X-Herald-Received-At`: incoming timestamp accepted by JavaScript `Date.parse()`, or a timestamp minted when absent or invalid; use timezone-qualified ISO 8601 for backend compatibility
- `X-Herald-Relay-Via`: sanitized incoming relay path with `edgeone` or `cloudflare` appended

The backend only trusts these headers after normal ingest-key authentication.

## Config

The backend exports endpoint digests from `GET /api/edge-config` with `Authorization: Bearer $EDGE_SYNC_TOKEN`.

```json
{
  "version": "sha-prefix",
  "updated_at": "2026-07-08T00:00:00+00:00",
  "ingest_endpoints": [
    { "id": "uuid", "key_sha256": "hex" }
  ]
}
```

Relays cache a successfully loaded config for 60 seconds and retain the last cached value if loading fails. A successful `/admin/config` write resets the cache in the handling isolate; it is not a global cache invalidation guarantee. From the repo root, an operator with the backend export token and relay admin token can push config to both relays with the project's Python 3.13+ interpreter (`python3` below must be at least 3.10 for this script):

```bash
EDGE_SYNC_TOKEN="$EDGE_SYNC_TOKEN" RELAY_ADMIN_TOKEN="$RELAY_ADMIN_TOKEN" \
  python3 scripts/sync_edge_config.py \
    --backend https://backend.example.com \
    --edges https://cf.example.workers.dev,https://edge.example.cn
```

Create, revoke, delete, or disable an endpoint/user on the backend first, then re-run sync before relying on the change at the relay. Both relays in this command must share the supplied admin token; use separate invocations if their tokens differ. The script tries all listed relays and exits nonzero if any push fails. Fix and retry failed pushes, then compare `/admin/status` config versions. Config skew can reject new endpoint keys with `401`; an upstream `401` is permanent and dead-letters a buffered envelope rather than retrying it. Revocations are still enforced at the backend even while a relay has stale config.

## Admin Endpoints

Both relays expose:

- `GET /healthz`
- `POST /admin/config`
- `GET /admin/status`
- `POST /relay/drain`

`/healthz` is public and only reports relay liveness; it does not check config, storage, or upstream delivery. The other endpoints require `Authorization: Bearer $RELAY_ADMIN_TOKEN`. `/admin/status` returns pending count, dead count, oldest pending timestamp, and config version. EdgeOne also returns a `truncated` flag when its capped KV scan cannot establish complete counts. `/relay/drain` forces a bounded batch even when backoff has not elapsed. Its `dead` count is the total retained dead count on Cloudflare but the number newly dead-lettered by that invocation on EdgeOne; use `/admin/status` for backlog totals.

Permanent upstream statuses are `400`, `401`, `403`, `404`, `413`, `415`, and `422`. Other failures retry with exponential backoff from 5 seconds, capped at 1 hour. When processed, pending envelopes older than 7 days move to dead records with the ingest key redacted. Drain activity removes dead records older than 30 days (EdgeOne scans at most 50 dead keys per pass); these are implemented cleanup thresholds, not guaranteed deletion deadlines or a statement of data obligations. There is no dead-record replay API.

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

Authenticate Wrangler for the intended account before any remote write. See the [official secret workflow](https://developers.cloudflare.com/workers/configuration/secrets/); `wrangler secret put` itself deploys a Worker version. Commands from `edge/`:

```bash
npm ci
npm test
npm run lint
npm run dev
npm run deploy
```

Use Node.js 24, as in CI. `npm run dev` is a local Cloudflare preview; it still requires usable local bindings and config. After deployment, sync endpoint config and check `/healthz` plus authenticated `/admin/status` before directing senders to the relay.

## EdgeOne

- Entry: `edge/edgeone/edge-functions/[[default]].js`
- Build helper: `edge/edgeone/build.sh`
- Buffer: Pages KV keys prefixed with `p_`
- Dead records: Pages KV keys prefixed with `d_`
- Retry: immediate background forward, then opportunistic drain on new ingest; manual GitHub Actions fallback
- Drain batch: 20 pending keys

EdgeOne Pages injects the KV binding as global `EDGE_CONFIG`, not `context.env.EDGE_CONFIG`. `context.env` must provide `UPSTREAM_URL` and `RELAY_ADMIN_TOKEN`.

Provisioning requirements:

- Create or link the EdgeOne Pages project.
- In the EdgeOne Pages console, create a Pages KV namespace and bind it to the project with binding name `EDGE_CONFIG`. EdgeOne injects this as a global variable, not on `context.env`.
- Set `UPSTREAM_URL` to the Cloudflare Worker base URL.
- Set `RELAY_ADMIN_TOKEN` as an EdgeOne environment variable.
- Deploy the function, then run `scripts/sync_edge_config.py` so `/admin/config` writes the active endpoint digest config.

Install and authenticate the [EdgeOne CLI](https://pages.edgeone.ai/document/edgeone-cli) for the intended account/site before deployment; it is not pinned in `edge/package-lock.json`. The provider currently retains `pages` commands as transition-compatible aliases of `makers` commands. For an authorized deployment, run from `edge/edgeone/`:

```bash
bash build.sh
npx edgeone pages link
npx edgeone pages deploy
```

The operator must confirm regional availability and domain/filing prerequisites for the selected EdgeOne service before directing traffic to it. The repository does not establish an account's region, domain eligibility, or ICP filing status.

## Drain Fallback

The checked-in [workflow](../.github/workflows/edge-drain.yml) exposes only `workflow_dispatch`; the five-minute cron example is commented out. It does **not** provide periodic retry during idle traffic. An operator can configure repository secrets and run the workflow manually:

- `EDGEONE_DRAIN_URL`: full EdgeOne drain URL including `/relay/drain`, for example `https://edge.example.cn/relay/drain`
- `RELAY_ADMIN_TOKEN`

If idle-time retry is required, the operator must explicitly arrange a scheduler; enabling one is a separate operational decision. Check authenticated `/admin/status` after draining, repeat bounded drains while needed, and investigate retained failures/dead records rather than treating an HTTP-successful drain as proof of delivery. Only the backend worker delivers to providers.
