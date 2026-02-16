Production deployment assets.

Files:
- `docker-compose.yml`: production compose that runs prebuilt images.
- `.env.example`: compose variable substitutions (images + DB creds).
- `db.env.example`: Postgres container env.
- `backend.env.example`: backend runtime env.
- `frontend.env.example`: frontend runtime env.

Typical usage:
- Create `deploy/.env`, `deploy/db.env`, `deploy/backend.env`, `deploy/frontend.env` from the corresponding `.example` files.
- Run from repo root:
  - `docker compose -f deploy/docker-compose.yml up -d`
