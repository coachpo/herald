#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
mode="${1:-serve}"
case "$mode" in
  --help|-h)
    echo 'Usage: ./start.sh [serve|dev]'
    echo 'serve: build the dashboard and run the single API/delivery process (default)'
    echo 'dev: run the API and Vite on ports 8000 and 35173'
    exit 0 ;;
  serve|dev) ;;
  *) echo 'Usage: ./start.sh [serve|dev]' >&2; exit 2 ;;
esac
[ "$#" -le 1 ] || { echo 'Too many arguments' >&2; exit 2; }
for tool in uv node corepack; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done
node -e 'if (Number(process.versions.node.split(".")[0]) !== 24) process.exit(1)'
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
export HERALD_DATA_DIR="${HERALD_DATA_DIR:-$ROOT_DIR/data}"
export HERALD_HOST="${HERALD_HOST:-127.0.0.1}"
export HERALD_PORT="${HERALD_PORT:-8000}"
uv sync --project backend --locked
corepack pnpm@10.30.1 --dir frontend install --frozen-lockfile
if [ "$mode" = serve ]; then
  corepack pnpm@10.30.1 --dir frontend build
  exec "$ROOT_DIR/backend/.venv/bin/herald-backend"
fi
if [ "$HERALD_PORT" != 8000 ]; then
  echo 'Vite development proxy requires HERALD_PORT=8000' >&2
  exit 2
fi
api_pid=''
vite_pid=''
cleanup() {
  trap - EXIT INT TERM
  [ -z "$api_pid" ] || kill "$api_pid" 2>/dev/null || true
  [ -z "$vite_pid" ] || kill "$vite_pid" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM
( exec "$ROOT_DIR/backend/.venv/bin/herald-backend" ) &
api_pid=$!
( cd "$ROOT_DIR/frontend"; exec ./node_modules/.bin/vite --host 127.0.0.1 --port 35173 --strictPort ) &
vite_pid=$!
wait -n "$api_pid" "$vite_pid"
