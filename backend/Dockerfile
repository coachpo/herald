FROM node:24-bookworm-slim AS frontend
ENV NODE_USE_ENV_PROXY=1
WORKDIR /build/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi; \
    corepack pnpm@10.30.1 install --frozen-lockfile
COPY frontend/ ./
RUN corepack pnpm@10.30.1 build

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" HERALD_DATA_DIR=/data HERALD_HOST=0.0.0.0
WORKDIR /app
RUN groupadd --gid 10001 herald && useradd --uid 10001 --gid herald herald \
    && mkdir -m 0700 /data && chown herald:herald /data
COPY --from=uv /uv /uvx /bin/
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./backend/
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --project backend --locked --no-dev --no-install-project
COPY backend/ ./backend/
COPY VERSION ./VERSION
COPY scripts/backup_db.sh ./scripts/backup_db.sh
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca; fi; \
    uv sync --project backend --locked --no-dev \
    && chmod -R a+rX /app
USER herald
EXPOSE 8000
CMD ["herald-backend"]
