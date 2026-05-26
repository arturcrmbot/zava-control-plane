#!/usr/bin/env bash
# Container entrypoint: run Azure Functions host (Durable orchestrator,
# :7071) in the background, then exec uvicorn on :80 as PID 1's child.
#
# The FastAPI server polls http://localhost:7071 at startup; if func
# doesn't bind within ~120s it warns and continues without Durable
# orchestration (workflow spawns will fail until func is up).
set -euo pipefail

FUNC_PORT="${FUNC_PORT:-7071}"
PORT="${PORT:-80}"

# Stream both processes' output to container stdout/stderr.
echo "[entrypoint] starting Azure Functions host on :${FUNC_PORT}"
(
  cd /app/api/functions
  # PYTHONPATH=/app so worker can import `api.*` modules.
  PYTHONPATH=/app exec func host start --port "${FUNC_PORT}" --no-build 2>&1 \
    | sed -u 's/^/[func] /'
) &
FUNC_PID=$!

cleanup() {
  echo "[entrypoint] caught signal; shutting down (func pid=${FUNC_PID})"
  kill -TERM "${FUNC_PID}" 2>/dev/null || true
  wait "${FUNC_PID}" 2>/dev/null || true
}
trap cleanup TERM INT

echo "[entrypoint] starting uvicorn on :${PORT}"
exec uvicorn api.server.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
