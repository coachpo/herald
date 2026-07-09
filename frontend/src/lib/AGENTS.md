# frontend/src/lib/AGENTS.md

## Overview

Shared frontend contract layer for API URLs, authenticated fetches, auth state, JSON helpers, DTO types, and utility classes. Changes here affect most dashboard routes.

## Files

| File | Role |
| --- | --- |
| `api.ts` | `apiFetch`, JSON parsing, API/request error normalization |
| `auth.tsx` | `AuthProvider`, login/logout/refresh, token storage |
| `authed.ts` | Bearer-token fetch with one refresh retry on `401` |
| `public-api.ts` | `VITE_API_URL` normalization and ingest URL generation |
| `types.ts` | Backend DTOs consumed by pages |
| `json.ts`, `utils.ts` | Display formatting and class-name helpers |

## Auth Rules

- Refresh token stays in `sessionStorage` under `herald_refresh_token`.
- Access token stays only in React state.
- `refresh()` de-duplicates in-flight refresh requests and schedules renewal before JWT expiry.
- `authedFetch()` retries once after `401`; do not add unbounded retry loops.
- `apiFetch()` must keep `credentials: "omit"` because auth is bearer-token based.

## API URL Rules

- `buildPublicApiUrl()` strips credentials, path, query, and hash from `VITE_API_URL`.
- Non-local `http://` origins are upgraded to `https://`.
- `buildIngestUrl()` converts dashed UUIDs to dashless hex for public ingest URLs.

## Do Not

- Do not change token storage without updating `AuthProvider`, `AuthGate`, and account/login flows together.
- Do not paper over DTO drift with casts; update `types.ts` and affected page code.
- Do not let `apiFetch()` start sending cookies or browser credentials.
