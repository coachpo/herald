#!/usr/bin/env bash
# Production deployments can use: docker compose up (FastAPI + PostgreSQL + worker)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
DB_PORT="${DB_PORT:-35432}"
BACKEND_PORT="${BACKEND_PORT:-38000}"
FRONTEND_PORT="${FRONTEND_PORT:-35173}"
MODE="${1:-${START_MODE:-full}}"
CLEANED_UP=false

usage() {
    echo "Usage: $0 [headless|full]"
    echo ""
    echo "Modes:"
    echo "  headless  Start Docker PostgreSQL + backend"
    echo "  full      Start Docker PostgreSQL + backend + frontend (default)"
    echo ""
    echo "Ports:"
    echo "  db        ${DB_PORT}"
    echo "  backend   ${BACKEND_PORT}"
    echo "  frontend  ${FRONTEND_PORT}"
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

compose_db() {
    POSTGRES_PORT="$DB_PORT" docker compose -f "$COMPOSE_FILE" "$@"
}

kill_pid_gracefully() {
    local pid="$1"

    if [[ -z "$pid" ]]; then
        return
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        return
    fi

    kill "$pid" 2>/dev/null || true

    for _ in {1..5}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            return
        fi
        sleep 1
    done

    kill -9 "$pid" 2>/dev/null || true
}

kill_process_tree() {
    local pid="$1"
    local child_pid=""

    if [[ -z "$pid" ]]; then
        return
    fi

    if ! kill -0 "$pid" 2>/dev/null; then
        return
    fi

    while IFS= read -r child_pid; do
        [[ -n "$child_pid" ]] && kill_process_tree "$child_pid"
    done < <(pgrep -P "$pid" 2>/dev/null || true)

    kill_pid_gracefully "$pid"
}

stop_docker_containers_on_port() {
    local port="$1"

    if ! command -v docker >/dev/null 2>&1; then
        return
    fi

    local container_ids=()
    while IFS= read -r container_id; do
        [[ -n "$container_id" ]] && container_ids+=("$container_id")
    done < <(docker ps --format '{{.ID}} {{.Ports}}' | grep ":${port}->" | awk '{print $1}' || true)

    if ((${#container_ids[@]})); then
        echo "Stopping Docker container(s) bound to port $port: ${container_ids[*]}"
        docker stop "${container_ids[@]}" >/dev/null || true
    fi
}

free_tcp_port() {
    local port="$1"
    local label="$2"

    stop_docker_containers_on_port "$port"

    local pids=()
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && pids+=("$pid")
    done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)

    if ((${#pids[@]})); then
        echo "Stopping ${label} listener(s) on port $port: ${pids[*]}"
        kill "${pids[@]}" 2>/dev/null || true
        sleep 1
    fi

    local stubborn_pids=()
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && stubborn_pids+=("$pid")
    done < <(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)

    if ((${#stubborn_pids[@]})); then
        echo "Force killing ${label} listener(s) on port $port: ${stubborn_pids[*]}"
        kill -9 "${stubborn_pids[@]}" 2>/dev/null || true
    fi
}

wait_for_db() {
    local container_id=""
    local status=""

    for _ in {1..60}; do
        container_id="$(compose_db ps -q db 2>/dev/null || true)"
        if [[ -n "$container_id" ]]; then
            status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id" 2>/dev/null || true)"
            if [[ "$status" == "healthy" || "$status" == "running" ]]; then
                return 0
            fi
        fi
        sleep 1
    done

    echo "Database container did not become ready in time."
    compose_db logs db || true
    return 1
}

wait_for_listener() {
    local port="$1"
    local label="$2"
    local attempts="$3"

    for _ in $(seq 1 "$attempts"); do
        if lsof -tiTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done

    echo "${label} did not start listening on port $port in time."
    return 1
}

cleanup() {
    if [ "$CLEANED_UP" = true ]; then
        return
    fi
    CLEANED_UP=true
    trap - EXIT INT TERM

    echo ""
    echo "Shutting down..."
    kill_process_tree "${FRONTEND_PID:-}"
    kill_process_tree "${BACKEND_PID:-}"
    compose_db stop db >/dev/null 2>&1 || true
    wait 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

if [ ! -d "$BACKEND_DIR" ]; then
    echo "Missing backend directory: $BACKEND_DIR"
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Missing docker compose file: $COMPOSE_FILE"
    exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required but not installed."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but not installed."
    exit 1
fi

if ! command -v lsof >/dev/null 2>&1; then
    echo "lsof is required but not installed."
    exit 1
fi

if ! command -v pgrep >/dev/null 2>&1; then
    echo "pgrep is required but not installed."
    exit 1
fi

if [ "$START_FRONTEND" = true ] && ! command -v pnpm >/dev/null 2>&1; then
    echo "pnpm is required for frontend mode but not installed."
    exit 1
fi

if [ "$START_FRONTEND" = true ] && [ ! -d "$FRONTEND_DIR" ]; then
    echo "Missing frontend directory: $FRONTEND_DIR"
    exit 1
fi

echo "Clearing listeners on ports $DB_PORT, $BACKEND_PORT, and $FRONTEND_PORT..."
compose_db rm -sf db >/dev/null 2>&1 || true
free_tcp_port "$DB_PORT" "database"
free_tcp_port "$BACKEND_PORT" "backend"
free_tcp_port "$FRONTEND_PORT" "frontend"

echo "Starting PostgreSQL on port $DB_PORT..."
compose_db up -d db
wait_for_db

# --- Backend setup ---
if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv "$BACKEND_DIR/.venv"
fi

echo "Installing backend dependencies..."
"$BACKEND_DIR/.venv/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

if [ "$START_FRONTEND" = true ]; then
    # --- Frontend setup ---
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "Installing frontend dependencies..."
        (cd "$FRONTEND_DIR" && pnpm install)
    fi

    # Keep local auth and API calls working when frontend runs on a custom port.
    export APP_BASE_URL="http://localhost:$FRONTEND_PORT"
    export CORS_ALLOWED_ORIGINS="http://localhost:$FRONTEND_PORT,http://127.0.0.1:$FRONTEND_PORT"
fi

export DATABASE_URL="postgresql://herald:herald@127.0.0.1:$DB_PORT/herald_dev"

echo "Ensuring local database schema..."
"$BACKEND_DIR/.venv/bin/python" "$BACKEND_DIR/bootstrap_dev_db.py"

# --- Start backend ---
echo "Starting backend on port $BACKEND_PORT..."
(cd "$ROOT_DIR" && exec "$BACKEND_DIR/.venv/bin/uvicorn" backend.main:app --host 0.0.0.0 --port "$BACKEND_PORT") &
BACKEND_PID=$!
wait_for_listener "$BACKEND_PORT" "Backend" 30

if [ "$START_FRONTEND" = true ]; then
    # --- Start frontend ---
    # Frontend calls backend directly via VITE_API_URL.
    echo "Starting frontend on port $FRONTEND_PORT..."
    (cd "$FRONTEND_DIR" && VITE_API_URL="http://localhost:$BACKEND_PORT" exec pnpm exec vite --host 0.0.0.0 --port "$FRONTEND_PORT") &
    FRONTEND_PID=$!
    wait_for_listener "$FRONTEND_PORT" "Frontend" 60
fi

echo ""
echo "========================================="
echo "  Herald"
echo "  Mode:     $MODE"
echo "  Database: postgresql://herald:herald@127.0.0.1:$DB_PORT/herald_dev"
echo "  Backend:  http://localhost:$BACKEND_PORT"
if [ "$START_FRONTEND" = true ]; then
    echo "  Frontend: http://localhost:$FRONTEND_PORT"
else
    echo "  Frontend: disabled (headless mode)"
fi
echo "========================================="
echo ""
echo "Press Ctrl+C to stop all managed services."
echo ""

wait
