# edge

Cloudflare and EdgeOne relay package for Herald.

## Layout

- `shared/`: protocol helpers used by both relay implementations
- `cloudflare/`: Worker and Durable Object buffer
- `edgeone/`: Pages function and build helper
- `tests/`: Node test suite

## Commands

```bash
npm install
npm test
npm run lint
npm run dev
npm run deploy
```

## Cloudflare

```bash
npm run dev
npm run deploy
```

Configure `edge/cloudflare/wrangler.toml` with the KV namespace and Durable Object migration.

## EdgeOne

```bash
cd edgeone
bash build.sh
npx edgeone pages link
npx edgeone pages deploy
```

The build step copies `shared/*.mjs` into `edgeone/edge-functions/_shared/`.

## Config

Use `scripts/sync_edge_config.py` from the repo root to push backend endpoint digests to each relay's `/admin/config` endpoint.
