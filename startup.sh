#!/usr/bin/env bash
# SahayakSetu — local dev launcher.
#
# Boots the FastAPI backend (uvicorn :8000) and the Vite frontend (:5173)
# together, with prefixed logs streaming into one terminal. Ctrl+C stops both.
#
# What it handles automatically:
#   • Creates a Python venv at .venv/ if missing and installs requirements.txt.
#   • Runs npm ci in frontend/ if node_modules is missing.
#   • Verifies the env vars the backend will refuse to start without (QDRANT_URL,
#     OPENROUTER_API_KEY) and warns about missing-but-required-in-prod ones.
#   • Frees ports 8000 and 5173 if they're stuck on a dead process.
#
# Usage:  ./startup.sh
#         ./startup.sh --reinstall      # blow away .venv and frontend deps first

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_LOG="$ROOT/.backend.log"
FRONTEND_LOG="$ROOT/.frontend.log"

REINSTALL=0
for arg in "$@"; do
  case "$arg" in
    --reinstall) REINSTALL=1 ;;
    -h|--help)
      sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "✗ Unknown flag: $arg" >&2; exit 2 ;;
  esac
done

# ---- Helpers --------------------------------------------------------------------

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

free_port() {
  local port="$1"
  local pids
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$pids" ]; then
    yellow "▸ Port $port busy (pid: $pids) — terminating"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [ -n "$pids" ]; then
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  fi
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { red "✗ Required command not found: $1"; exit 1; }
}

# ---- Pre-flight -----------------------------------------------------------------

require_cmd python3
require_cmd npm
require_cmd lsof

if [ ! -f "$ROOT/.env" ]; then
  red "✗ .env missing at $ROOT/.env"
  echo "  cp .env.example .env  # then fill in QDRANT_URL and OPENROUTER_API_KEY"
  exit 1
fi

# Source .env into a subshell so we can validate without polluting our shell —
# the actual processes will load it via python-dotenv from $ROOT/.env.
ENV_VARS="$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT/.env" || true)"
get_env() { printf '%s\n' "$ENV_VARS" | awk -F= -v k="$1" '$1==k {sub("^"k"=",""); print; exit}'; }

QDRANT_URL_VAL="$(get_env QDRANT_URL)"
OPENROUTER_API_KEY_VAL="$(get_env OPENROUTER_API_KEY)"
ENV_VAL="$(get_env ENV)"
ENV_VAL="${ENV_VAL:-development}"

[ -z "$QDRANT_URL_VAL" ] && { red "✗ QDRANT_URL is empty in .env (backend won't import)"; exit 1; }
[ -z "$OPENROUTER_API_KEY_VAL" ] && { red "✗ OPENROUTER_API_KEY is empty in .env (backend won't import)"; exit 1; }

if [ "$ENV_VAL" = "production" ]; then
  for var in SESSION_SECRET VAPI_WEBHOOK_SECRET MONGODB_URL BACKEND_URL FRONTEND_ORIGIN; do
    val="$(get_env "$var")"
    if [ -z "$val" ]; then
      red "✗ ENV=production but $var is empty — backend will refuse to start"
      exit 1
    fi
  done
fi

# ---- Python venv ----------------------------------------------------------------

if [ "$REINSTALL" -eq 1 ]; then
  yellow "▸ --reinstall: removing $VENV"
  rm -rf "$VENV"
fi

if [ ! -d "$VENV" ]; then
  yellow "▸ Creating Python venv at $VENV ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install --upgrade pip >/dev/null
  yellow "▸ Installing requirements.txt (this can take a minute on first run) ..."
  "$VENV/bin/pip" install -r "$ROOT/requirements.txt"
  green "✓ venv ready"
fi

# Light sanity check — if a key dep is missing the venv was probably wiped.
if ! "$VENV/bin/python" -c "import fastapi, uvicorn, qdrant_client" >/dev/null 2>&1; then
  yellow "▸ venv looks incomplete — re-installing requirements.txt"
  "$VENV/bin/pip" install -r "$ROOT/requirements.txt"
fi

# ---- Frontend deps --------------------------------------------------------------

if [ "$REINSTALL" -eq 1 ]; then
  yellow "▸ --reinstall: removing $FRONTEND/node_modules and $FRONTEND/node_modules/.vite"
  rm -rf "$FRONTEND/node_modules"
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  yellow "▸ Installing frontend dependencies ..."
  if [ -f "$FRONTEND/package-lock.json" ]; then
    npm --prefix "$FRONTEND" ci
  else
    npm --prefix "$FRONTEND" install
  fi
  green "✓ frontend deps ready"
fi

# Always wipe Vite's resolver cache — cheap and avoids the stale-cache "failed to
# resolve import" errors after refactors.
rm -rf "$FRONTEND/node_modules/.vite"

# ---- Free ports + log files ----------------------------------------------------

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

# ---- Process management --------------------------------------------------------

BACKEND_PID=""
FRONTEND_PID=""
TAIL_BE=""
TAIL_FE=""

cleanup() {
  echo ""
  yellow "▸ Stopping…"
  for pid in "$TAIL_BE" "$TAIL_FE" "$BACKEND_PID" "$FRONTEND_PID"; do
    [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  done
  # Belt-and-braces: if anything is clinging to the ports, knock it off.
  free_port "$BACKEND_PORT" >/dev/null 2>&1 || true
  free_port "$FRONTEND_PORT" >/dev/null 2>&1 || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

green "▸ Backend  → http://localhost:$BACKEND_PORT  (docs: /docs)"
"$VENV/bin/python" -m uvicorn backend.main:app --reload --port "$BACKEND_PORT" \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

green "▸ Frontend → http://localhost:$FRONTEND_PORT"
npm --prefix "$FRONTEND" run dev -- --port "$FRONTEND_PORT" --strictPort \
  > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "  Backend  PID $BACKEND_PID  (log: $BACKEND_LOG)"
echo "  Frontend PID $FRONTEND_PID (log: $FRONTEND_LOG)"
echo "  Ctrl+C to stop both."
echo ""

# Stream both logs into the terminal with a prefix so it's clear which is which.
(sed -u 's/^/[backend]  /' < <(tail -F "$BACKEND_LOG" 2>/dev/null)) &
TAIL_BE=$!
(sed -u 's/^/[frontend] /' < <(tail -F "$FRONTEND_LOG" 2>/dev/null)) &
TAIL_FE=$!

# Wait on whichever child exits first. macOS ships Bash 3.2 which has no `wait -n`,
# so we poll instead — sleep 1s, check both PIDs, exit the loop the moment either
# stops responding to kill -0.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

# One of the services died on its own — surface why before cleanup tears the rest down.
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
  red "✗ Backend exited. Last 40 log lines:"
  tail -n 40 "$BACKEND_LOG" | sed 's/^/[backend]  /'
fi
if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
  red "✗ Frontend exited. Last 40 log lines:"
  tail -n 40 "$FRONTEND_LOG" | sed 's/^/[frontend] /'
fi

cleanup
