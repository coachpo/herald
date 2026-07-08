# Production Upgrade Verification

Date: 2026-07-08
Branch: `production-upgrade`

## Automated Checks

| Check | Result |
| --- | --- |
| `uv run --project backend --locked pytest backend/tests -v` | `118 passed, 8 warnings` |
| `npm --prefix edge test` | `21 passed` |
| `npm --prefix edge run lint` | passed |
| `corepack pnpm@10.30.1 --dir frontend lint` | passed |
| `corepack pnpm@10.30.1 --dir frontend build` | passed |
| `python3 scripts/sync_version.py --check` | `Aligned version: 0.9.0` |
| `npx wrangler deploy --dry-run -c cloudflare/wrangler.toml` from `edge/` | passed |

## Guard Checks

| Check | Result |
| --- | --- |
| `beacon_`, `accounts_`, old secret name, old bootstrap script outside design/plan docs | no matches |
| removed user-verification field outside design/plan docs | no matches |
| newly added `TODO` or `FIXME` outside design/plan docs | no matches |
| backend non-test code line delta versus `main` | net `-838` lines |

## Runtime Rehearsals

| Scenario | Evidence |
| --- | --- |
| Fresh local helper startup | `./start.sh headless` ran migrations and started backend on `38000`; `curl -fsS http://localhost:38000/health` returned `{"status":"ok","database":"connected","version":"0.9.0"}` |
| Production compose secret guard | `docker compose config` without required secrets failed; with `POSTGRES_PASSWORD`, `SECRET_KEY`, and `CHANNEL_CONFIG_ENCRYPTION_KEY` it rendered successfully |
| Worker crash recovery | backend worker tests cover stale `sending` sweep back to `retry` and subsequent delivery processing |
| Relay upstream outage and recovery | edge tests cover Cloudflare Durable Object retry/dead/status paths and EdgeOne KV temporary failure, successful drain, permanent dead-letter, cache TTL, and status paths |
| OpenAPI alignment | generated FastAPI schema matches `docs/openapi.yaml`; ingest includes relay headers and `200` duplicate response; edge config includes Bearer security |

## Release-Time External Steps

These require provider credentials or hosted infrastructure and are not reproducible inside the local repository workspace:

- EdgeOne hosted `pages link/dev/deploy` against the production account and KV binding.
- Public-domain Cloudflare to backend to provider end-to-end delivery.
- Mainland EdgeOne route using an ICP-filed domain when serving China mainland traffic.
