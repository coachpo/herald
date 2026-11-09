# Operations

Commands run from the repository root unless stated otherwise. One resident application process serves HTTP, the built UI, and provider delivery. MQTT sends use bounded short-lived child processes, terminated and joined on timeout/cancellation. Keep its data directory on persistent local storage; network filesystems and multiple runtime instances are unsupported.

## Local startup

Requires Python 3.13+, uv, Node.js 24, and Corepack:

```bash
./start.sh
```

This installs locked dependencies, builds `frontend/dist`, and runs `herald-backend`. `./start.sh dev` runs the API on 8000 and Vite on 35173 with same-origin API proxying. It stops only children it started and fails if required ports are occupied. Do not run a second API against the same data directory.

Manual equivalent:

```bash
uv sync --project backend --locked
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend build
uv run --project backend --locked herald-backend
```

Schema initialization and SQLite v1-to-v2 migration are automatic after acquiring the exclusive data-directory lock. There is no external database, separate migration job, or separate worker command. Older PostgreSQL databases are not imported. Back up an existing SQLite store before upgrading; see [Schema upgrades](#schema-upgrades).

## Credentials

The default data directory is `./data`. First startup (or `herald-backend init`) creates private `credentials.env` (mode 600), containing `HERALD_ADMIN_TOKEN`, `HERALD_INGEST_TOKEN`, and `HERALD_ENCRYPTION_KEY`. The data directory must have mode 700; existing less-private directories are rejected rather than silently changed. Use a private operator session to obtain only the token needed; do not paste credentials into logs, issue trackers, chat, or source files. The CLI reports the location without printing values.

Give the management token to the owner for dashboard login and the ingest token to senders. Keep the encryption key private and backed up. To override generated credentials, set all three credential variables together; partial overrides fail. Preserve the encryption key for existing targets.

The application reads process environment, not arbitrary `.env` files. `start.sh` loads an optional root `.env`; Compose reads it for interpolation. Create one only if needed, without overwriting an existing file:

```bash
test -e .env || cp .env.example .env
chmod 600 .env
```

## Container

```bash
docker compose up -d --build
docker compose logs --tail=100 herald
```

The root build context uses `backend/Dockerfile` to build the UI and backend into one image. The `herald` service stores SQLite and credentials in the `herald_data` named volume and publishes only `127.0.0.1:8000`. The container runs as uid/gid 10001. Bind mounts, if substituted, must be writable by that user. `HERALD_DATA_DIR` in the container is always `/data`; changing a host-shell variable does not relocate the named volume.

Use `docker compose stop herald` before offline maintenance. `docker compose down` retains the named volume; never use `down -v` unless you intend to delete the instance and credentials. Do not scale the service. The data-directory lock rejects a second process, and SQLite is local single-instance storage.

For remote access, terminate TLS in a reverse proxy and explicitly route it to the loopback port. Keep tokens out of URLs and proxy logs. The application ignores forwarded headers; authenticate with bearer tokens.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `HERALD_DATA_DIR` | `./data` | SQLite, credentials, process lock; `/data` in Compose |
| `HERALD_HOST` | `127.0.0.1` | HTTP bind; container uses `0.0.0.0` internally |
| `HERALD_PORT` | `8000` | HTTP port; Compose variable chooses host port |
| `HERALD_DELIVERY_TIMEOUT` | `10` | Per-attempt provider timeout, seconds |
| `HERALD_MAX_ATTEMPTS` | `5` | Attempts per automatic/manual retry cycle |
| `HERALD_BACKOFF_BASE` | `5` | Initial retry delay, seconds |
| `HERALD_BACKOFF_MAX` | `300` | Maximum retry delay, seconds |
| `HERALD_CONCURRENCY` | `4` | Maximum concurrent provider attempts |
| `HERALD_RETENTION_DAYS` | `30` | Successful-history cleanup threshold |
| `HERALD_ADMIN_TOKEN` | generated | Management API/dashboard credential |
| `HERALD_INGEST_TOKEN` | generated | External receive-only credential |
| `HERALD_ENCRYPTION_KEY` | generated | Fernet key for target configuration |

Worker settings must be positive. Credential tokens must differ and contain at least 32 characters. Run only one HTTP worker. Later attempts read the current target configuration, so edits can change where pending jobs are sent. Disabling a target excludes it from new receipts; already accepted jobs still run. Inspect pending work before modifying destinations.

## Routing configuration

Manage rules in the existing Targets workspace or with the admin-only `GET/PUT /api/routing` endpoints. Saving replaces the complete ordered array using the revision last read. On `409 routing_changed`, reload and reconcile edits rather than overwriting another saved configuration. Clearing rules is a valid revisioned update. Before deleting a target, remove every rule reference, including disabled rules; referenced targets return `409 target_referenced_by_routing` and targets with unfinished work remain protected.

Automatic sends use all enabled matching rules, with each rule's conditions ANDed and all matched targets deduplicated. Only zero matching rules fall back to enabled defaults. Every selected target must exist and be enabled, otherwise the whole receipt fails; there is no partial receipt or silent default fallback for an unavailable matched target. A nonempty explicit target list bypasses routing. No matching/default targets produces `400 no_targets`. See [API](04_api_spec.md#routing-configuration) for condition operators and validation.

Rules and default flags affect new receipts only. A repeated idempotent request returns its original receipt before evaluating current rules or target availability. Recorded decisions contain the mode, revision, and matched rule IDs, not a historical copy of rules or addresses. Existing deliveries never reroute during retries or recovery, but they read the current target configuration on claim; inspect pending work before changing credentials or destinations.

## Delivery and recovery

An accepted receipt means SQLite committed the message and every selected delivery. Provider failures retry with exponential backoff, then remain `failed` after the attempt-cycle limit. Use the dashboard or `POST /api/deliveries/{id}/retry` to retry an individual failure; successful deliveries are not resent. Each attempt increments total and cycle counters before sending.

Startup recovers `sending` deliveries interrupted by a crash. A provider may already have received one, so duplicates are possible. This is at-least-once delivery. Keep senders' idempotency keys stable when retrying receipt requests; do not reuse a key for a different payload.

There is no cleanup scheduler. The dashboard or `POST /api/cleanup` triggers cleanup, which only removes messages for which every delivery succeeded and the last completion exceeds the retention threshold. Pending and failed records are retained. Targets with unfinished work or rule references cannot be deleted. Check outstanding work and disk space during operations; provider/network failures do not justify deleting the queue.

## Backup and restore

`scripts/backup_db.sh` uses SQLite's online backup API to create a consistent `herald.sqlite3` plus a private copy of `credentials.env` in a new timestamped directory. Backups contain sensitive data and credentials; restrict access. It does not install a schedule or delete old backups. If credentials come from the environment instead, back them up separately in your secret manager.

For local runs:

```bash
HERALD_DATA_DIR=/absolute/path/to/data BACKUP_DIR=/private/backups ./scripts/backup_db.sh
```

For Compose, use the same script inside the container and copy the generated directory to protected storage:

```bash
docker compose exec -T herald sh -c 'HERALD_DATA_DIR=/data BACKUP_DIR=/tmp/herald-backups /app/scripts/backup_db.sh'
# Copy the specific backup directory reported above; destination must be private.
docker compose cp herald:/tmp/herald-backups/<backup-directory> /private/backups/
```

For restore, stop all writers and preserve the current data directory first. Restore the backed-up SQLite file and the matching credential file into an empty replacement directory with owner-only permissions (directory 700, credential file 600). If environment credentials were used, supply that same encryption key. Do not restore a database over a running process, copy a live database without its WAL, or mix a database with unrelated keys. Point the instance at the replacement directory, start it, check `/health`, inspect targets/history, and verify queued delivery recovery. Provider effects may repeat after restoring older queue state.

## Schema upgrades

Before replacing a v1 application, use the existing backup procedure above to preserve its database and matching credentials, then stop its writer. Start the new application against that same protected data directory. After obtaining the existing exclusive process lock, startup upgrades v1 to v2 in one transaction: create `routing_config` at revision 0 with no rules, add nullable message routing decisions, and update `PRAGMA user_version`. DDL, initial configuration, and version roll back together if migration fails. Existing message IDs, idempotency fingerprints/keys, delivery states and counters, encrypted configurations, foreign keys, and uniqueness constraints are preserved. Old messages display no recorded routing explanation; existing queued work keeps its selected targets.

New stores initialize directly at v2. Repeated initialization does not reset saved routing or its revision, and an unsupported higher version is rejected. There is no downgrade migration and no promise that the old application can read a v2 database. To roll back an upgrade, stop the new writer, preserve its state, and restore the original v1 backup with its matching credentials before starting the old version. Restoring an older queue can repeat provider effects. Never replace a live database or discard unfinished work merely to downgrade.

## Validation

```bash
uv run --project backend --locked pytest backend/tests -q
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
python3 scripts/sync_version.py --check
```

Tests use temporary SQLite files and mocked providers. `GET /health` returns `503` for database failure or a stopped delivery task. A delivery-result database failure stops the loop instead of silently losing work; resolve the storage problem and restart the instance so startup recovery requeues interrupted work. A healthy API does not prove an external provider delivered a message.
