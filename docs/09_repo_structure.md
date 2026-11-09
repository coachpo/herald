# Repository guide

| Path | Owns |
| --- | --- |
| `backend/config.py`, `security.py` | Private local credentials and separate bearer-token authentication |
| `backend/api.py`, `models.py` | HTTP input/output contract |
| `backend/database.py` | SQLite schema v2 initialization and transactional v1 migration |
| `backend/store.py` | Atomic receipt/routing selection, revisioned rule configuration, claims, retries, cleanup |
| `backend/routing.py` | Pure priority/title/body matching and union of all matching rule targets |
| `backend/worker.py` | Bounded in-process provider dispatch |
| `backend/channel_dispatch.py`, `providers/`, `core/` | Provider formatting, encryption, and outbound safety |
| `backend/app.py`, `cli.py` | Single-process lifecycle, data-directory lock, API/UI |
| `frontend/` | Single-user React dashboard and Vite development |
| `scripts/` | Version alignment and consistent SQLite backups |
| `docker-compose.yml`, `backend/Dockerfile`, `start.sh` | Single-service packaging and startup |
| `docs/` | Architecture, data, API, security, and operations |

## Development principles

Keep the durable path direct: validate and fingerprint the request, check idempotency inside the write transaction, select targets from explicit IDs or one routing revision, atomically store message/decision/jobs, then dispatch outside the transaction. The fingerprint excludes routing results. Defaults apply only when no rule matches. Retries use persisted deliveries, never reroute, and successful deliveries remain untouched. Use short cohesive modules, explicit ownership, and standard-library SQLite instead of adding infrastructure. Split code only when responsibilities become hard to navigate.

Keep routing configuration and receipt selection in Store's SQLite transactions; the pure matcher must not access the database or network. Configuration changes affect new messages, while attempts read the latest target configuration rather than a snapshot. Rule order preserves configuration and explanation order, not execution priority. The existing Targets workspace owns rule management through a separate editor component/hook; message details display the recorded routing explanation without reconstructing old rules.

Record uncertain platform limits as assumptions rather than inventing conservative caps or abuse policies. Use the supported best-case path and revisit assumptions when evidence or accepted requirements changes. This does not weaken existing credential, SSRF, privacy, or durability requirements.

`VERSION` is the source of package versions. `scripts/sync_version.py` updates backend and frontend metadata; `--check` verifies without changing them. API schema is generated from the app; documentation must describe current behavior, not retained obsolete designs.
