# Repo structure — Beacon Spear v1.0

Beacon Spear is organized as a small “meta” repository:

- Root repo: design docs + top-level coordination
- `backend/` git submodule: Django backend + worker
- `frontend/` git submodule: React 19 + Vite dashboard UI
- `edge/` git submodule: edge forwarders (Cloudflare Workers, Tencent EdgeOne)

## Why submodules

- Backend and frontend can evolve independently.
- Separate dependency trees and release cycles.
- Clear ownership boundaries.

## Conventions

- Dashboard uses React 19 + Vite + React Router; pin versions in `package.json`.
- Backend remains Django-based; worker can be implemented as a Django management command or separate worker entrypoint.
- Keep `/api/*` reserved for backend routes so a reverse proxy can route cleanly.

## First-time setup

```
git submodule update --init --recursive
```

## Submodule URLs

When you create the real remote repositories for `backend` and `frontend`, set each submodule URL in `.gitmodules` and commit the update.
