# Herald

Herald ingests structured JSON over HTTP, stores messages in PostgreSQL, and forwards matching messages to Bark, ntfy, MQTT, or Gotify.

## Packages

- `backend/`: FastAPI API, migrations, PostgreSQL access, auth, ingest, and delivery worker
- `frontend/`: React 19 + Vite dashboard
- `edge/`: Cloudflare and EdgeOne store-and-forward relays

## Features

- Email/password signup, login, refresh-token rotation, account changes, and CLI password reset
- Multiple ingest endpoints with one-time raw keys
- JSON ingest with message history, filters, detail view, soft delete, and batch delete
- Bark, ntfy, MQTT, and Gotify channels
- Rules with endpoint/body/priority/tag/group filters and payload templates
- Durable Cloudflare relay and EdgeOne KV relay for cross-border ingress

## Quick Start

```bash
./start.sh headless
./start.sh full
```

Manual backend startup from repo root:

```bash
uv sync --project backend --locked
uv run --project backend --locked python -m backend.migrate
uv run --project backend --locked herald-backend
uv run --project backend --locked python -m backend.worker
```

Production compose:

```bash
export POSTGRES_PASSWORD='<database password>'
export SECRET_KEY='<random backend secret>'
export CHANNEL_CONFIG_ENCRYPTION_KEY='<fernet key>'
export EDGE_SYNC_TOKEN='<random sync token>'
docker compose up -d
```

## Docs

- `docs/01_prd.md`: product scope
- `docs/02_architecture.md`: runtime architecture
- `docs/03_data_model.md`: database tables
- `docs/04_api_spec.md`: API guide
- `docs/openapi.yaml`: generated OpenAPI schema
- `docs/06_security_privacy.md`: keys, trust boundaries, SSRF
- `docs/07_operations.md`: deployment and operations
- `docs/10_edge.md`: Cloudflare and EdgeOne relay protocol

## Verification

```bash
uv run --project backend --locked pytest backend/tests -v
npm --prefix edge test && npm --prefix edge run lint
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
python3 scripts/sync_version.py --check
```
