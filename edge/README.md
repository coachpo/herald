# edge - Herald Lite

Cloudflare Worker package for Herald lite mode: local rule evaluation, template rendering, and Bark/ntfy HTTP dispatch driven by a KV snapshot.

## Routes

- `GET /healthz` - returns `{"ok": true, "mode": "lite"}`
- `POST /api/ingest/{endpoint_id}` - validate payload, match rules, dispatch HTTP notifications

## Runtime Model

- Reads config from KV binding `EDGE_CONFIG`, key `config`
- Evaluates filters locally using the exported `rules` array
- Renders `payload_template` values with Mustache-style `{{...}}` substitution
- Dispatches only Bark and ntfy over HTTP
- Does not persist messages, queue retries, or support MQTT

## Important Auth Caveat

Current lite-mode behavior compares `X-Herald-Ingest-Key` directly against the exported `token_hash` string from the KV snapshot. It does not hash the incoming header before comparison. Keep docs and clients accurate to that current implementation.

## Config Shape

The backend exports config with:

- `ingest_endpoints`: `{id, name, token_hash}`
- `channels`: Bark/ntfy channels only, each with decrypted `config`
- `rules`: `{id, name, filter, channel_id, payload_template}`
- `updated_at`, `version`

See `docs/10_edge.md` for the maintained reference.

## Local Dev

```bash
npm install
npm run dev
```

## Tests And Lint

```bash
npm test
npm run lint
```

## Deploy

```bash
npx wrangler kv namespace create EDGE_CONFIG
# update wrangler.toml with the namespace id
npx wrangler kv key put --namespace-id=<ns_id> config '<json blob>'
npm run deploy
```
