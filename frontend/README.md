## Herald Frontend

React 19 + Vite + React Router dashboard for Herald.

## Local dev

Requires Node.js 24 and pnpm 10.30.1 (the versions declared in `package.json`). From the repository root:

```bash
cd frontend
corepack pnpm@10.30.1 install --frozen-lockfile
corepack pnpm@10.30.1 dev
```

Defaults:
- frontend: `http://localhost:3000`
- when `VITE_API_URL` is unset, requests use the page origin; Vite proxies `/api` and `/health` to `http://localhost:8000`. Start the backend separately using [Operations](../docs/07_operations.md).
- to call a backend directly, set its origin in `frontend/.env.local`, for example `VITE_API_URL=http://localhost:8000`, and configure the backend's `CORS_ALLOWED_ORIGINS` to include the frontend origin. API URL normalization strips paths, credentials, queries, and fragments; non-local HTTP origins are upgraded to HTTPS.
- the repository helper `./start.sh full` instead uses frontend port `35173` and points `VITE_API_URL` at its API on `http://localhost:38000`. It does not start the delivery worker.

`VITE_API_URL` is a development/build-time setting, not a runtime setting of the static server. The frontend Dockerfile builds `dist/` and serves it with `deploy/server.mjs` on port `3100`, with SPA fallback and no API proxy. The root Compose files do not deploy this frontend.

## Validation and behavior

From `frontend/`, run `corepack pnpm@10.30.1 lint` and `corepack pnpm@10.30.1 build`; there is no frontend test script. Route and screen behavior is documented in the [UI Spec](../docs/05_ui_spec.md), auth/key handling in [Security and Privacy](../docs/06_security_privacy.md), and shared contribution principles in [Repo Structure](../docs/09_repo_structure.md#development-principles).

## UI (shadcn/ui)

This app uses shadcn/ui-style components under `src/components/ui/`.

Add new primitives from the shadcn registry (run from `frontend/`):

```bash
npx shadcn@latest add <component>
```

Notes:
- Tailwind is configured in `src/globals.css` (Tailwind v4, CSS-first).
- Global tokens live in `src/globals.css` (`--background`, `--foreground`, `--radius`, etc.).
