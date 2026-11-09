# Repository guide

| Path | Owns |
| --- | --- |
| `backend/config.py`, `security.py` | Private local credentials and separate bearer-token authentication |
| `backend/api.py`, `models.py` | HTTP input/output contract |
| `backend/store.py` | SQLite schema, atomic receipt, claims, retries, cleanup |
| `backend/worker.py` | Bounded in-process provider dispatch |
| `backend/channel_dispatch.py`, `providers/`, `core/` | Provider formatting, encryption, and outbound safety |
| `backend/app.py`, `cli.py` | Single-process lifecycle, data-directory lock, API/UI |
| `frontend/` | Single-user React dashboard and Vite development |
| `scripts/` | Version alignment and consistent SQLite backups |
| `docker-compose.yml`, `backend/Dockerfile`, `start.sh` | Single-service packaging and startup |
| `docs/` | Architecture, data, API, security, and operations |

## Development principles

Keep the durable path direct: validate and select targets, atomically store receipt/jobs, then dispatch outside the transaction. Use short cohesive modules, explicit ownership, and standard-library SQLite instead of adding infrastructure. Split code only when responsibilities become hard to navigate.

Record uncertain platform limits as assumptions rather than inventing conservative caps or abuse policies. Use the supported best-case path and revisit assumptions when evidence or accepted requirements changes. This does not weaken existing credential, SSRF, privacy, or durability requirements.

`VERSION` is the source of package versions. `scripts/sync_version.py` updates backend and frontend metadata; `--check` verifies without changing them. API schema is generated from the app; documentation must describe current behavior, not retained obsolete designs.
