# edge

Cloudflare and EdgeOne relay package for Herald. The backend remains responsible for rules and provider delivery. See [Edge Relay](../docs/10_edge.md) for protocol, provisioning, config sync, and drain procedures.

## Layout

- `shared/`: protocol helpers used by both relay implementations
- `cloudflare/`: Worker and Durable Object buffer
- `edgeone/`: Pages function and build helper
- `tests/`: Node test suite

## Commands

Run from `edge/` with Node.js 24:

```bash
npm ci
npm test
npm run lint
npm run dev
```

`npm test` first rebuilds the generated EdgeOne `_shared/` copy. `npm run dev` starts the Cloudflare relay, not EdgeOne. Ingest also needs relay config and the bindings described in the [relay guide](../docs/10_edge.md).

## Cloudflare

For an authorized deployment, configure `cloudflare/wrangler.toml`, provision the KV/DO bindings, authenticate Wrangler, and set the admin secret before running `npm run deploy` from `edge/`. The checked-in namespace and upstream URL are placeholders; see [Cloudflare provisioning](../docs/10_edge.md#cloudflare).

## EdgeOne

After provisioning the project, binding, environment, and CLI authentication in the [EdgeOne guide](../docs/10_edge.md#edgeone), deploy from `edge/edgeone/`:

```bash
bash build.sh
npx edgeone pages link
npx edgeone pages deploy
```

The build step copies `shared/*.mjs` into `edgeone/edge-functions/_shared/`; edit only the canonical files in `shared/`. EdgeOne CLI is not a locked dependency of this package.

## Config

Use the [config sync procedure](../docs/10_edge.md#config) from the repo root after endpoint changes. The [drain fallback](../docs/10_edge.md#drain-fallback) is manual in the checked-in workflow; there is no enabled periodic EdgeOne drain.
