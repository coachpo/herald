# AGENTS.md

Herald is a single-user SQLite store-and-forward service. One FastAPI process owns the API, built dashboard, and bounded delivery worker. Read the [repository guide](docs/09_repo_structure.md) and subtree guidance before editing.

## Shared constraints

- Preserve durable receipt: commit the message and every selected delivery before returning success. Both send APIs use the same Store operation.
- Preserve SQLite WAL, synchronous FULL, foreign keys, short transactions, and exclusive process locking. Never add a second resident application/worker process or network calls inside transactions.
- Keep management and ingest tokens separate, hash before constant-time comparison, encrypt target configurations, and never log or commit secrets.
- Keep SSRF destination/DNS checks, TLS verification, and HTTP redirect restrictions. DNS validation and client connection are separate; do not claim address pinning. Never render message content as HTML or store tokens in localStorage.
- Delivery is at least once. Preserve idempotency conflicts, failed-only manual retry, successful delivery history, and retention of all unfinished work.
- Do not add `as any`, `@ts-ignore`, or `@ts-expect-error`.
- `VERSION` owns backend/frontend package versions; run `python3 scripts/sync_version.py --check`.
- Do not hand-edit generated `docs/openapi.yaml`; generate it from `create_app().openapi()` using a temporary data directory, without starting services.

## Commands

From the repository root, Python 3.13+, uv, Node.js 24, and Corepack:

```bash
uv sync --project backend --locked
uv run --project backend --locked pytest backend/tests -q
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
./start.sh
```

Tests use temporary SQLite stores. `./start.sh dev` also starts Vite; production needs only the single backend process and persistent data directory. Existing cloud tasks are already isolated: use the provided checkout and do not create a worktree unless requested.

Documentation-only edits need source/link review and `git diff --check`, not unrelated full suites. Detailed setup and backup procedures belong in [Operations](docs/07_operations.md).
