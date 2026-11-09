# frontend/AGENTS.md

## Commands

Requires Node 24 and pnpm 10.30.1. From the repository root:

```bash
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
corepack pnpm@10.30.1 --dir frontend dev
corepack pnpm@10.30.1 --dir frontend lint
corepack pnpm@10.30.1 --dir frontend build
```

There is no frontend test runner. Verify changes with lint plus the production build. Preview uses `corepack pnpm@10.30.1 --dir frontend preview` after building.

## Change Boundaries

- Routes live in `src/router.tsx`; `AuthLayout`/`DashboardLayout` supply auth and `AuthGate` protects dashboard routes.
- Shared API/auth/DTO changes belong in `src/lib/`; check its local guide and affected protected pages together.
- Keep provider-specific channel form defaults and validators together under `src/pages/dashboard/channels/`.
- Page state is local React state; no query/client-state library is configured.
- Tokens and browser credentials follow the `src/lib/` guide; root security restrictions still apply.
- Global design tokens and Tailwind v4 configuration live in `src/globals.css`; reusable primitives live in `src/components/ui/`.
- `VITE_API_URL` is a build-time public API origin, not a secret or runtime container setting. When empty, browser requests use the dashboard origin; do not assume Vite proxying also exists in production.
- Production Docker serving uses `deploy/server.mjs`, not nginx or Vite preview. See the [frontend README](README.md) and [Operations](../docs/07_operations.md#frontend-production).
