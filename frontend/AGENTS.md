# Frontend

Requires Node 24 and pnpm 10.30.1. Run from the repository root:

```bash
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend dev
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
```

The UI is React with plain CSS. `App.tsx` authenticates one management token and switches between `Messages.tsx` and `Targets.tsx`. There is no router, account system, rule engine, template editor, or frontend test runner. Validate changes with lint, production build, and affected browser flows.

- Requests always use the page origin and `credentials: "omit"`. Vite proxies `/api` and `/health` to the backend on port 8000 during development.
- Production uses the backend to serve `frontend/dist`; no separate frontend server/container is needed.
- Keep management tokens in sessionStorage under `herald_admin_token`; never localStorage. Never embed credentials or ingest tokens in bundles or copied examples.
- Target credentials are omitted by read APIs. Empty secret fields during editing must be omitted from PUT config so the server preserves existing values.
- Only failed deliveries expose manual retry. Receipt/queued status is not delivery success. Sent deliveries must not have a replay action.
- Render message bodies and errors as text, never HTML. Keep fields aligned with `backend/models.py`, `backend/target_config.py`, and `backend/api.py`.
