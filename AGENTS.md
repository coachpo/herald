# AGENTS.md

This repo is a three-package app:

- `backend/`: Django + DRF JSON API, plus a delivery worker
- `frontend/`: Next.js dashboard UI (proxies `/api/*` to the backend)
- `edge/`: Edge forwarders (Cloudflare Workers, Tencent EdgeOne)

For package-specific commands and conventions, prefer the closest file:

- `backend/AGENTS.md`
- `frontend/AGENTS.md`
- `edge/AGENTS.md`

## Quick Start (Dev)

- Backend API: see `backend/AGENTS.md`
- Frontend UI: see `frontend/AGENTS.md`

## Security Notes

- Do not commit secrets (tokens, passwords, `.env` contents).
- Treat third-party endpoints as untrusted input. Backend has SSRF protections; keep them intact.

## Repo Structure

- `docs/`: PRD/specs, OpenAPI (`docs/openapi.yaml`)
- `backend/`: Django project
- `frontend/`: Next.js project
