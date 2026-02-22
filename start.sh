#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
MODE="${1:-${START_MODE:-headless}}"
CLEANED_UP=false

usage() {
    echo "Usage: $0 [headless|full]"
    echo ""
    echo "Modes:"
    echo "  headless  Start backend only (default)"
    echo "  full      Start backend + frontend"
    echo ""
    echo "You can also set START_MODE=headless|full."
}

if [[ "${MODE}" == "-h" || "${MODE}" == "--help" ]]; then
    usage
    exit 0
fi

if [[ "$#" -gt 1 ]]; then
    usage
    exit 1
fi

case "$MODE" in
    headless)
        START_FRONTEND=false
        ;;
    full)
        START_FRONTEND=true
        ;;
    *)
        echo "Invalid mode: $MODE"
        usage
        exit 1
        ;;
esac

cleanup() {
    if [ "$CLEANED_UP" = true ]; then
        return
    fi
    CLEANED_UP=true

    echo ""
    echo "Shutting down..."
    [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

if [ ! -d "$BACKEND_DIR" ]; then
    echo "Missing backend directory: $BACKEND_DIR"
    exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Missing frontend directory: $FRONTEND_DIR"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but not installed."
    exit 1
fi

if [ "$START_FRONTEND" = true ] && ! command -v pnpm >/dev/null 2>&1; then
    echo "pnpm is required for frontend mode but not installed."
    exit 1
fi

# --- Backend setup ---
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

echo "Installing backend dependencies..."
"$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

echo "Applying backend migrations..."
(cd "$BACKEND_DIR" && "$BACKEND_DIR/.venv/bin/python" manage.py migrate --noinput)

if [ "$START_FRONTEND" = true ]; then
    # --- Frontend setup ---
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "Installing frontend dependencies..."
        (cd "$FRONTEND_DIR" && pnpm install)
    fi

    # Keep local auth and API calls working when frontend runs on a custom port.
    export APP_BASE_URL="${APP_BASE_URL:-http://localhost:$FRONTEND_PORT}"
    export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT}"
fi

# --- Start backend ---
echo "Starting backend on port $BACKEND_PORT..."
(cd "$BACKEND_DIR" && "$BACKEND_DIR/.venv/bin/python" manage.py runserver "0.0.0.0:$BACKEND_PORT") &
BACKEND_PID=$!

if [ "$START_FRONTEND" = true ]; then
    # --- Start frontend ---
    # Frontend calls backend directly via VITE_API_URL.
    echo "Starting frontend on port $FRONTEND_PORT..."
    (cd "$FRONTEND_DIR" && VITE_API_URL="http://localhost:$BACKEND_PORT" pnpm exec vite --host 0.0.0.0 --port "$FRONTEND_PORT") &
    FRONTEND_PID=$!
fi

echo ""
echo "========================================="
echo "  Herald"
echo "  Mode:     $MODE"
echo "  Backend:  http://localhost:$BACKEND_PORT"
if [ "$START_FRONTEND" = true ]; then
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
else
    echo "  Frontend: disabled (headless mode)"
fi
echo "  Admin:    http://localhost:$BACKEND_PORT/admin"
echo "========================================="
echo ""

wait
