# Herald

English | [简体中文](README_CN.md)

Herald is a self-hosted notification hub: one inbox for notifications from all your machines, scripts, and services, fanned out to the app you already use. It ingests structured JSON over HTTP, stores messages in PostgreSQL, and forwards matching messages to Bark, ntfy, MQTT, or Gotify.

## Packages

- [`backend/`](backend/README.md): FastAPI API, migrations, PostgreSQL access, auth, ingest, and delivery worker
- [`frontend/`](frontend/README.md): React 19 + Vite dashboard
- [`edge/`](edge/README.md): Cloudflare and EdgeOne store-and-forward relays

## Features

- Email/password auth with refresh-token rotation, account management, and CLI password reset
- Multiple ingest endpoints with reusable raw keys shown only at creation
- Browsable message history with filtering, detail view, and soft or batch delete
- Bark, ntfy, MQTT, and Gotify channels
- Delivery rules that match on message body, priority, and group, with per-rule payload templates
- Endpoint and tag filters can be saved and previewed, but currently prevent live rule matches; see [rule limitations](docs/04_api_spec.md#rules)
- Durable Cloudflare relay and EdgeOne KV relay for unreliable network paths

## Quick Start

From the repository root, choose one local helper mode. Requires Docker Compose, Python 3.13+, uv, `lsof`, and `pgrep`; full mode also needs Node 24 and pnpm 10.30.1 on `PATH`.

```bash
./start.sh headless  # PostgreSQL + API
# OR
./start.sh full      # PostgreSQL + API + dashboard
```

The helper stops existing containers/listeners on ports `35432`, `38000`, and `35173` by default, including the frontend port in headless mode. It does **not** start the delivery worker. In another terminal, using the default helper database port:

```bash
DATABASE_URL=postgresql://herald:herald@127.0.0.1:35432/herald_dev \
  uv run --project backend --locked python -m backend.worker
```

Adjust the URL if `DB_PORT` was overridden. See [local development](docs/07_operations.md#local-development) for ports and alternative startup paths, or the [backend quick start](backend/README.md#quick-start) for manual startup. For production, follow [Production Compose](docs/07_operations.md#production-compose), then deploy the frontend and any relays separately; the root Compose file only runs backend services.

## Docs

These documents own the detailed contracts; package READMEs are focused entry points and `AGENTS.md` files contain agent instructions, not a second project manual.

| Authority | Document |
| --- | --- |
| Product intent, implemented scope, non-goals | [Product scope](docs/01_prd.md) |
| Current components and data/control flow | [Architecture](docs/02_architecture.md) |
| Persistent schema | [Data model](docs/03_data_model.md) |
| HTTP behavior, provider configs, known API limitations | [API guide](docs/04_api_spec.md) |
| Browser routes and user flows | [UI specification](docs/05_ui_spec.md) |
| Keys, trust boundaries, safety, privacy constraints | [Security and privacy](docs/06_security_privacy.md) |
| Setup, validation commands, deployment, backup/recovery | [Operations](docs/07_operations.md) |
| Bark payload details | [Bark v2](docs/08_bark_v2.md) |
| Package boundaries and shared development principles | [Repository structure](docs/09_repo_structure.md) |
| Relay protocol, platform configuration, edge procedures | [Edge runbook](docs/10_edge.md) |
| Generated schema snapshot; not the complete manual ingest contract | [OpenAPI](docs/openapi.yaml) |

Repository documentation describes implementation and intended workflows. Actual deployments, user counts, service commitments, and applicable retention obligations are not established by repository contents.

## Verification

Use the package checks in [Operations](docs/07_operations.md#local-development), matching [CI](.github/workflows/ci.yml). Backend tests automatically migrate and truncate business tables: point `TEST_DATABASE_URL` only at a dedicated disposable PostgreSQL database, never a database whose data you need to keep. Frontend checks are lint and production build; edge checks are tests and syntax lint. Version alignment is `python3 scripts/sync_version.py --check` from the repository root.
