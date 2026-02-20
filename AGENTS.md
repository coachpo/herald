# AGENTS.md

**Generated:** 2026-02-20 **Commit:** 8256b0b **Branch:** main

## Overview

Beacon Spear — ingest arbitrary UTF-8 payloads via HTTP, store them, and forward to notification channels (Bark, ntfy, MQTT) via user-defined rules. Three independent packages connected by HTTP APIs; no shared code.

## Structure

```
beacon-spear/
├── backend/        # Django 5 + DRF JSON API + delivery worker
├── frontend/       # Next.js 16 (App Router) dashboard UI
├── edge/           # Cloudflare Worker — lite mode (local rules, no backend)
├── docs/           # PRD, architecture, data model, API spec, OpenAPI
├── deploy/         # docker-compose.yml (Postgres + backend + worker + frontend)
└── .github/        # CI: Docker image builds (arm64), cleanup
```

Git submodules: `backend/` and `frontend/` are submodules (see `.gitmodules`).

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| Domain models | `backend/beacon/models.py` | IngestEndpoint, Message, Channel, ForwardingRule, Delivery |
| Auth (JWT, users) | `backend/accounts/` | Custom User (email-only), refresh token rotation with family_id |
| API endpoints | `backend/api/urls.py` | All routes under `/api/` |
| Ingest handler | `backend/api/ingest.py` | POST `/api/ingest/{endpoint_id}` (UUID or hex) |
| Delivery worker | `backend/beacon/management/commands/deliveries_worker.py` | Polling loop, exponential backoff |
| SSRF protection | `backend/beacon/ssrf.py` | Blocks loopback/private IPs for outbound URLs |
| Channel encryption | `backend/beacon/crypto.py` | Fernet encryption for `Channel.config_json_encrypted` |
| Frontend auth | `frontend/lib/auth.tsx` | AuthProvider context, sessionStorage refresh tokens |
| Frontend API client | `frontend/lib/api.ts` | `apiFetch()` — direct browser-to-backend, `credentials: "omit"` |
| Frontend types | `frontend/lib/types.ts` | TypeScript types mirroring backend API responses |
| Edge config | `edge/src/lite.mjs` | KV-based config, local rule eval + HTTP dispatch |
| OpenAPI spec | `docs/openapi.yaml` | JSON API + ingest endpoints |
| Docker deploy | `deploy/docker-compose.yml` | Postgres + backend:8100 + worker + frontend:3100 |

## Package Communication

```
Frontend (browser) --NEXT_PUBLIC_API_URL--> Backend (/api/*)
Backend --edge-config endpoint--> Edge (KV push)
Edge (standalone) --HTTP dispatch--> Bark/ntfy
Backend worker --HTTP/MQTT dispatch--> Bark/ntfy/MQTT
```

No server-side proxy. Frontend calls backend directly from browser.

## Conventions

- Custom implementations over third-party packages: JWT auth (not simplejwt), CORS middleware (not django-cors-headers), .env loader (not python-dotenv), DATABASE_URL parser (not dj-database-url)
- All UUIDs are v4, used as primary keys across all models
- Soft-delete pattern: `deleted_at` / `revoked_at` / `disabled_at` nullable timestamps
- Channel configs encrypted at rest with Fernet (`CHANNEL_CONFIG_ENCRYPTION_KEY`)
- Ingest endpoints accept both dashed UUID and dashless hex formats
- Backend serves on port 8100 in Docker (not 8000)

## Anti-Patterns (Do Not)

- **Never disable SSRF checks** in `beacon/ssrf.py` — blocks loopback, link-local, private networks
- **Never log secrets** — device keys, access tokens, passwords, ingest keys
- **Never commit `.env` files** or any credential material
- **Never persist tokens in localStorage** — sessionStorage only (XSS = account takeover with JWT)
- **Never use `dangerouslySetInnerHTML`** — all ingested payloads are untrusted plain text
- **Never suppress type errors** — no `as any`, `@ts-ignore`, `@ts-expect-error`

## Commands

```bash
# Backend (from backend/)
python manage.py migrate --noinput
python manage.py test
python manage.py runserver 0.0.0.0:8000

# Worker (from backend/)
python manage.py deliveries_worker

# Frontend (from frontend/)
pnpm install
pnpm lint
pnpm build
pnpm dev -p 3000

# Edge (from edge/)
npm install
npm test
npm run lint
npm run dev
```

## Environment Variables (Key)

| Variable | Package | Purpose |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | backend | Django secret (change from default) |
| `JWT_SIGNING_KEY` | backend | JWT token signing |
| `TOKEN_HASH_KEY` | backend | Ingest token hashing |
| `CHANNEL_CONFIG_ENCRYPTION_KEY` | backend | Fernet key for channel configs |
| `DATABASE_URL` | backend | Postgres connection (sqlite fallback) |
| `NEXT_PUBLIC_API_URL` | frontend | Backend URL (default: `http://localhost:8100`) |
| `CORS_ALLOWED_ORIGINS` | backend | Allowed frontend origins |
| `BARK_BLOCK_PRIVATE_NETWORKS` | backend | SSRF protection toggle (default: true) |

## CI/CD

- GitHub Actions: `docker-images.yml` builds arm64 Docker images on push to main/tags
- GHCR registry: `ghcr.io/{owner}/beacon-spear-backend`, `ghcr.io/{owner}/beacon-spear-frontend`
- Cleanup workflow: daily prune of old workflow runs + untagged container images

## Notes

- SQLite is default for local dev; settings auto-enables WAL mode + 30s timeout for multi-process (API + worker)
- Backend uses `NEXT_PUBLIC_BASE_URL` setting for email verification links (points to frontend)
- Edge has no durable retries or message persistence — best-effort HTTP dispatch only
- MQTT channel type is backend-only (no TCP sockets in Workers)
