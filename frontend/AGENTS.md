# frontend/AGENTS.md

## Overview

React 19 + Vite + React Router dashboard. Production requests go directly from the browser to the backend via `VITE_API_URL`.

## Command Notes

- Root `AGENTS.md` carries the normal frontend lint/build commands.
- Extra local commands are `corepack pnpm@10.30.1 --dir frontend install`, `corepack pnpm@10.30.1 --dir frontend dev`, and `corepack pnpm@10.30.1 --dir frontend preview`.

## Structure

```text
frontend/
├── src/components/
├── src/layouts/
├── src/lib/
├── src/pages/
├── src/router.tsx
├── src/main.tsx
└── deploy/server.mjs
```

## Routes

```text
/login /signup
/ /messages /messages/:id /channels /rules /ingest-endpoints /account
```

## Key Patterns

- `AuthLayout` and `DashboardLayout` provide `AuthProvider`.
- `AuthGate` refreshes on mount and redirects unauthenticated users to `/login?next=...`.
- Refresh token stays in `sessionStorage` key `herald_refresh_token`.
- Access token stays in React state.
- `apiFetch()` uses `credentials: "omit"`.
- `authedFetch()` retries once after refresh on `401`.
- `buildIngestUrl()` converts UUIDs to hex for public ingest URLs.
- `src/lib/` is high blast radius; check auth, API calls, and all protected pages when changing it.
- Page state is local React state; there is no query/client state library.
- Frontend has no test runner; verification is lint plus production build.

## UI Notes

- Dashboard home shows quick actions, recent messages, recent failures, and setup progress.
- Messages page exposes endpoint, priority-range, and time-range filters.
- Channels page supports create/delete/test for Bark, ntfy, MQTT, and Gotify.
- Rules page supports create, preview/test, list, and delete.
- Ingest endpoints page shows the key once at creation and provides copyable URL/curl examples.
- Account page handles change email, change password, and delete account.
- Channel form config is split under `pages/dashboard/channels/`; keep provider validators and defaults together.
- Production Docker serving uses `deploy/server.mjs`, not nginx or Vite preview.

## Do Not

- Do not store auth tokens in `localStorage`.
- Do not hardcode secrets into frontend code.
- Do not render ingested payloads as HTML.
