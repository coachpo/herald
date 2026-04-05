# frontend/AGENTS.md

## Overview

React 19 + Vite + React Router dashboard. Production requests go directly from the browser to the backend via `VITE_API_URL`; Vite's proxy is a local-dev convenience only.

## Commands

```bash
pnpm install
pnpm lint
pnpm build
pnpm dev
pnpm preview
```

## Structure

```text
frontend/
├── src/
│   ├── components/   # AppShell, AuthGate, forms, shadcn/ui primitives
│   ├── layouts/      # AuthLayout, DashboardLayout
│   ├── lib/          # api/auth/authed/public-api/types/utils
│   ├── pages/        # auth pages + dashboard pages
│   ├── router.tsx    # route tree
│   ├── main.tsx      # BrowserRouter bootstrap
│   └── globals.css   # Tailwind v4 tokens + theme styles
├── vite.config.ts    # port 3000, path alias, local proxy
├── components.json   # shadcn/ui registry config
└── deploy/server.mjs # static SPA server on port 3100
```

## Route Map

```text
/login /signup /forgot-password /reset-password /verify-email
/ /messages /messages/:id /channels /rules /ingest-endpoints /account
```

## Key Patterns

- `AuthLayout` and `DashboardLayout` both provide `AuthProvider`.
- `AuthGate` triggers an immediate refresh on mount and redirects unauthenticated users to `/login?next=...`.
- Refresh token lives in `sessionStorage` key `herald_refresh_token`; access token stays in React state.
- JWT auto-refresh is scheduled 60 seconds before expiry.
- `apiFetch()` injects `Authorization` and always uses `credentials: "omit"`.
- `authedFetch()` retries once after a successful refresh on `401`.
- `buildPublicApiUrl()` preserves localhost HTTP, upgrades non-localhost HTTP to HTTPS, and `buildIngestUrl()` converts UUIDs to hex for ingest URLs.
- Supported toolchain is Node `^24.0.0` with `pnpm@10.30.1`; there is no frontend test runner in `package.json`.
- `components.json` uses shadcn/ui `new-york` style, `lucide` icons, and Tailwind v4 tokens from `src/globals.css`.
- `pnpm dev` uses Vite port `3000`; `deploy/server.mjs` serves `dist/` on `3100`; `start.sh full` typically overrides Vite to `35173` and points `VITE_API_URL` at the helper backend port.
- `deploy/server.mjs` serves the built SPA with immutable asset caching and a `GET /health` endpoint.
- Forms use `useState` plus manual validation; `pnpm lint` plus `pnpm build` are the only package verification steps.
- Theme preference uses `localStorage` key `herald_theme` and `<html data-theme>`.
- Forgot/reset/verify pages assume tokens arrive out of band; the current backend does not implement repo-local email delivery.

## UI Notes

- Dashboard home shows quick actions, recent messages, recent failures, a getting-started list, and an unverified-email warning banner.
- Messages page exposes endpoint, priority-range, and time-range filters; batch delete also supports optional `ingest_endpoint_id`.
- Channels page supports create/delete for Bark, ntfy, MQTT, and Gotify plus live send-test calls.
- Channels page intentionally ships create/delete/test flows only; there is no channel edit surface.
- Rules page supports create, preview/test, list, and delete; the backend has read/update APIs, but the UI does not expose edit flows.
- Ingest endpoints page shows the key once at creation and provides copyable URL/curl examples; the backend has detail/rename routes, but the current UI only exposes create/list/revoke/archive.
- Account page handles resend verification requests, change email, change password, and delete account.

## Security (Do Not)

- Never store auth tokens in `localStorage`.
- Never hardcode secrets into frontend code or config.
- Never render ingested payloads as HTML.
- Never assume visible filter controls or auth pages imply backend support; confirm the corresponding API route behavior before updating docs.

## Verification

- Primary checks are `pnpm lint` and `pnpm build`.
- There is no Vitest/Jest setup in the current package.
