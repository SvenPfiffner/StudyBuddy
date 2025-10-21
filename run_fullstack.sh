#!/usr/bin/env bash
# Run both StudyBuddy backend and frontend concurrently with logging.
# Works on Linux and macOS.

set -euo pipefail

# ---------- Defaults (override via flags) ----------
HOST="0.0.0.0"
PORT="8000"

# ---------- Resolve paths ----------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_SCRIPT="$SCRIPT_DIR/run_backend.sh"
FRONTEND_SCRIPT="$SCRIPT_DIR/run_frontend.sh"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

timestamp="$(date +%Y%m%d-%H%M%S)"
BACKEND_LOG="$LOG_DIR/backend-$timestamp.log"
FRONTEND_LOG="$LOG_DIR/frontend-$timestamp.log"

# ---------- Checks ----------
ensure_exec() {
  local f="$1"
  if [ ! -f "$f" ]; then
    echo "Error: expected script not found: $f" >&2
    exit 1
  fi
  if [ ! -x "$f" ]; then
    chmod +x "$f" || {
      echo "Error: cannot make executable: $f" >&2
      exit 1
    }
  fi
}

ensure_exec "$BACKEND_SCRIPT"
ensure_exec "$FRONTEND_SCRIPT"

# ---------- Start services ----------
echo "Logs:"
echo "  Backend : $BACKEND_LOG"
echo "  Frontend: $FRONTEND_LOG"
echo

# Start backend
(
  cd "$SCRIPT_DIR"
  "$BACKEND_SCRIPT" --host "$HOST" --port "$PORT"
) >> "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# Start frontend
(
  cd "$SCRIPT_DIR"
  "$FRONTEND_SCRIPT"
) >> "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo "StudyBuddy ready. Access the frontend at http://localhost:3000"
echo "Press Ctrl+C to stop."

# ---------- Cleanup on exit ----------
terminate() {
  echo
  echo "Shutting down…"
  for pid in "$BACKEND_PID" "$FRONTEND_PID"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait || true
  echo "All services stopped."
}
trap terminate INT TERM EXIT

# ---------- Wait for both to finish ----------
# If either exits, wait will return when the remaining one exits or on Ctrl+C
wait
