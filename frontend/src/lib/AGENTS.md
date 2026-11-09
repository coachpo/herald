# API and DTOs

`api.ts` adds the management Bearer token to same-origin `/api` requests and uses `credentials: "omit"`. It preserves HTTP status in `ApiError` so the application clears authentication on 401. Do not log request headers or tokens.

`types.ts` describes the current single-user API. Change callers when contracts change rather than introducing legacy DTOs or casts that conceal mismatches. Ingest uses a separate token and is not called by the dashboard; the send form uses the authenticated management `/api/messages` endpoint.

Follow the frontend lint/build commands in its parent guide.
