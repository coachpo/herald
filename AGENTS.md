# AGENTS.md

## Where To Look

| Task | Location |
| --- | --- |
| Backend runtime and schema | `backend/app.py`, `backend/cli.py`, `backend/database.py`, `backend/migrations/`, `backend/migrate.py` |
| Auth | `backend/routes/auth.py`, `backend/services/auth.py`, `backend/auth/` |
| Ingest | `backend/routes/ingest.py`, `backend/services/ingest.py` |
| Delivery worker | `backend/worker.py`, `backend/channel_dispatch.py`, `backend/providers/` |
| Edge config export | `backend/routes/__init__.py`, `backend/edge_config.py` |
| Frontend routes and API/auth helpers | `frontend/src/router.tsx`, `frontend/src/lib/` |
| Edge relay | `edge/shared/` (canonical), `edge/cloudflare/`, `edge/edgeone/` |
| Local orchestration, sync, backup | `start.sh`, `docker-compose*.yml`, `scripts/` |

## Shared Constraints

- Follow subtree `AGENTS.md` files for package commands and local invariants. All command examples in these guides run from the repository root unless stated otherwise.
- Preserve SSRF enforcement in `backend/core/ssrf.py`, token hashing, channel-config encryption, and header redaction. Do not log or commit secrets.
- Do not store auth tokens in `localStorage`, render ingested payloads as HTML, or hardcode frontend secrets.
- Do not add `as any`, `@ts-ignore`, or `@ts-expect-error`.
- `VERSION` owns package versions. Use `scripts/sync_version.py` to synchronize its managed metadata; verify with `python3 scripts/sync_version.py --check`.
- Do not hand-edit generated EdgeOne `_shared/` modules or `docs/openapi.yaml`; follow the local generation guidance.

## Design and Development Defaults

Apply the [development principles](docs/09_repo_structure.md#development-principles): record uncertain capability/tier/quota assumptions using the looser supported option; assume legitimate requests without adding unrequested abuse handling or conservative limits; choose the best-case path and make worst-case handling an explicit decision. Revisit assumptions when authoritative limits, measured failures, or accepted requirements justify it. These defaults do not weaken existing security or privacy obligations.

Keep source files cohesive and navigable. Split along responsibilities when growth obscures behavior or review; respect existing size limits, but do not invent a universal line cap or fragment files merely to shorten them.

## Validation and Documentation

- Run the affected package checks listed in its guide; backend tests require a dedicated PostgreSQL database and truncate business tables.
- For documentation-only changes, inspect relevant definitions and links and use small non-destructive checks; do not start the full application or run unrelated suites. There is no dedicated documentation-check job in current CI.
- `start.sh` stops existing listeners/containers on its helper ports, even in headless mode. Do not run it just to inspect commands; `./start.sh --help` is non-starting. It does not start the delivery worker.
- Use the [README documentation index](README.md#docs) for canonical facts and [Operations](docs/07_operations.md) for setup, configuration, and operational procedures. Keep detailed project explanations out of agent guides.
