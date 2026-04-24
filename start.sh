#!/usr/bin/env bash
# Starts SahayakSetu backend (FastAPI :8000) and frontend (Vite :5173) together.
# Ctrl+C stops both.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

VENV="$ROOT/.venv"
FRONTEND="$ROOT/frontend"

if [ ! -d "$VENV" ]; then
  echo "✗ Python venv not found at $VENV"
  echo "  Create it with: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "▸ Installing frontend dependencies…"
  npm --prefix "$FRONTEND" install
fi

if [ ! -f "$ROOT/.env" ]; then
  echo "⚠ No .env found at repo root. Copy .env.example → .env and fill QDRANT_URL + GEMINI_API_KEY."
fi

# Log files (tailed into this terminal)
BACKEND_LOG="$ROOT/.backend.log"
FRONTEND_LOG="$ROOT/.frontend.log"
: > "$BACKEND_LOG"
: > "$FRONTEND_LOG"

cleanup() {
  echo ""
  echo "▸ Stopping…"
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

echo "▸ Starting backend  → http://localhost:8000  (docs at /docs)"
"$VENV/bin/python" -m uvicorn backend.main:app --reload --port 8000 > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "▸ Starting frontend → http://localhost:5173"
npm --prefix "$FRONTEND" run dev > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo ""
echo "  Backend  PID $BACKEND_PID  (log: $BACKEND_LOG)"
echo "  Frontend PID $FRONTEND_PID (log: $FRONTEND_LOG)"
echo "  Ctrl+C to stop both."
echo ""

# Tail both logs with prefixes so it's obvious which is which.
(sed -u 's/^/[backend]  /' < <(tail -f "$BACKEND_LOG")) &
TAIL_BE=$!
(sed -u 's/^/[frontend] /' < <(tail -f "$FRONTEND_LOG")) &
TAIL_FE=$!

trap 'kill $TAIL_BE $TAIL_FE 2>/dev/null || true; cleanup' INT TERM

wait "$BACKEND_PID" "$FRONTEND_PID"
