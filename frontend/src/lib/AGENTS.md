# frontend/src/lib/AGENTS.md

## Auth and API Contracts

- `auth.tsx`: refresh token stays in `sessionStorage` under `herald_refresh_token`; access token stays in React state. Refresh de-duplicates in-flight requests and schedules renewal before JWT expiry.
- `authed.ts`: `authedFetch()` retries once after a `401` and successful refresh. Do not add unbounded retry loops.
- `api.ts`: keep `credentials: "omit"` because auth is bearer-token based.
- Storage changes require checking `AuthProvider`, `AuthGate`, and account/login flows together.
- `types.ts` owns the DTOs consumed by pages; fix DTO drift and callers instead of hiding it with casts.

## Public URL Contracts

- `public-api.ts` normalizes configured `VITE_API_URL` to an origin by stripping credentials/path/query/hash. Empty config uses `window.location.origin`; non-local HTTP is upgraded to HTTPS.
- `buildIngestUrl()` converts dashed UUIDs to dashless hex for public ingest URLs.
- Check both authenticated API calls and copied public ingest URLs when changing URL handling; deployment paths must remain origin-based.
- Use the parent frontend lint/build checks after changes here.
