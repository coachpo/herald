# edge/AGENTS.md

## Commands

From the repository root, with Node 24:

```bash
npm --prefix edge ci
npm --prefix edge test
npm --prefix edge run lint
```

`npm test` runs `edgeone/build.sh` first. Cloudflare local development uses `npm --prefix edge run dev`; deployment is a separate external write, not a validation command. See the [edge runbook](../docs/10_edge.md) for bindings, secrets, and deployment.

## Runtime and Generated Boundaries

- Edit protocol/auth/validation in `edge/shared/`, the canonical source for both platforms. `edge/edgeone/edge-functions/_shared/` is generated; never edit it by hand. Run `bash edge/edgeone/build.sh` before EdgeOne dev/deploy.
- Cloudflare buffers in Durable Object SQLite with alarms. EdgeOne buffers in Pages KV with `p_` pending and `d_` dead keys.
- EdgeOne KV is bound through global `EDGE_CONFIG`, not `context.env.EDGE_CONFIG`.
- Keep `UPSTREAM_URL` fixed in deployment configuration, not request-controlled. Backend remains the rule/provider dispatch engine.
- Preserve valid incoming message-id/received-at headers and append the platform to relay-via. Shared protocol details belong in the `shared/` guide.
- Pending envelopes contain raw ingest keys; dead records must redact them.
- Admin config/status/drain routes require bearer `RELAY_ADMIN_TOKEN`. Do not confuse this with the backend's `EDGE_SYNC_TOKEN`.
- GitHub edge-drain scheduling is commented out; do not assume idle EdgeOne queues have a configured scheduled retry.
