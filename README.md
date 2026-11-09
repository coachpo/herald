# Herald

English | [简体中文](README_CN.md)

Herald is a single-user notification inbox and durable forwarding service. One process serves the dashboard and HTTP API, stores messages in SQLite, and delivers them to Bark, ntfy, MQTT, or Gotify.

External ingestion uses HTTP JSON at `POST /api/ingest`; MQTT is an outbound delivery target. This version removes the PostgreSQL service, user accounts, legacy templates, Edge relays, and their legacy APIs. The dashboard sends through the same durable receipt operation and can configure conditions for selecting forwarding targets.

A request is acknowledged only after its message and all selected delivery jobs are committed. Failed jobs retry automatically; the dashboard shows each target's state and allows retrying a terminal failure. Delivery is **at least once**: a crash after a provider accepts a message can cause a duplicate.

## Run

Requires Python 3.13+, uv, Node.js 24, and Corepack. From the repository root:

```bash
./start.sh
```

The helper installs locked dependencies, builds the dashboard, and runs the API and delivery loop together. Open the dashboard on port 8000. For separate Vite development, use `./start.sh dev`; Vite listens on port 35173 and proxies to the API on port 8000. Neither mode stops unrelated listeners.

The first start creates `data/herald.sqlite3` and private `data/credentials.env`. Use `HERALD_DATA_DIR` to choose another persistent directory. Retrieve `HERALD_ADMIN_TOKEN` privately from that file for dashboard login; give senders the separate `HERALD_INGEST_TOKEN`. Never share the encryption key. No signup, email, external database, or separate worker is needed.

Alternatively, run the single container with its persistent data volume:

```bash
docker compose up -d --build
```

See [Operations](docs/07_operations.md) for configuration, secure credential access, backup/restore, and upgrades. Existing SQLite schema v1 stores upgrade transactionally to v2; back up before upgrading. Older PostgreSQL databases are not imported.

## Send

Create enabled targets in the dashboard and configure routing rules or at least one default target, then send JSON using an ingest token already set securely in the shell:

```bash
curl --fail-with-body -X POST http://127.0.0.1:8000/api/ingest \
  -H "Authorization: Bearer $HERALD_INGEST_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"title":"Backup","body":"Backup completed","priority":3,"idempotency_key":"backup-2026-11-09"}'
```

Use a nonempty `target_ids` array to select targets explicitly and bypass rules and defaults. If omitted or `null`, all enabled matching rules contribute their target IDs; only zero matches fall back to all enabled default targets. Matching supports priority comparisons and case-sensitive title/body conditions. Targets are deduplicated, and every selected target must exist and be enabled; an empty selection is rejected without storing a message.

Rules and defaults affect new receipts only. Repeating the same idempotency key and payload returns the original result even after routing changes; changing the payload returns `409`. The request fingerprint does not include a routing revision or calculated targets. Existing jobs keep their selected targets, but later attempts use the targets' current configuration, not a snapshot. Omit the key to create a new message every time. `201` means stored for delivery, not delivered. See [API](docs/04_api_spec.md#routing-configuration) for rules and recorded decisions.

## Validate

```bash
uv sync --project backend --locked
uv run --project backend --locked pytest backend/tests -q
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
python3 scripts/sync_version.py --check
```

Tests use disposable SQLite files and mocked provider transports.

## Docs

- [Architecture](docs/02_architecture.md): process ownership and delivery flow
- [Data model](docs/03_data_model.md): durable records and cleanup
- [API](docs/04_api_spec.md): requests, authentication, and delivery states
- [Security](docs/06_security_privacy.md): credentials, provider protection, and privacy
- [Operations](docs/07_operations.md): startup, configuration, backup, and recovery
- [Repository guide](docs/09_repo_structure.md): source ownership and development principles
