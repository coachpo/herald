## Herald Frontend

React 19 + Vite + React Router dashboard for Herald.

## Local dev

```bash
pnpm install
cp .env.example .env.local
pnpm dev
```

Defaults:
- frontend: http://localhost:3000
- backend: provided via `VITE_API_URL` and called directly from the browser; `./start.sh full` points it at the helper backend port (`http://localhost:38000`)

## UI (shadcn/ui)

This app uses shadcn/ui-style components under `src/components/ui/`.

Add new primitives from the shadcn registry (run from `frontend/`):

```bash
npx shadcn@latest add <component>
```

Notes:
- Tailwind is configured in `src/globals.css` (Tailwind v4, CSS-first).
- Global tokens live in `src/globals.css` (`--background`, `--foreground`, `--radius`, etc.).
