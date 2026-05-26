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

# In replay mode the Durable orchestrator never fires — every workflow
# event is replayed from the baked tape. Skip the Functions host
# entirely so the container is leaner and there's no AzureWebJobsStorage
# dependency at runtime.
if [[ "${ZAVA_MODE:-live}" == "replay" ]]; then
  echo "[entrypoint] ZAVA_MODE=replay → skipping Functions host"
  echo "[entrypoint] ZAVA_TAPE_PATH=${ZAVA_TAPE_PATH:-/app/tape/tape.tar.gz}"
  echo "[entrypoint] starting uvicorn on :${PORT}"
  exec uvicorn api.server.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
fi

# Stream both processes' output to container stdout/stderr.
echo "[entrypoint] starting Azure Functions host on :${FUNC_PORT}"
# Kuzu (entity graph) holds an exclusive file lock per process. uvicorn
# opens data/portal/entity_graph.kuzu first, so the func worker — which
# imports the same substrate module-tree via function_app.py — would
# crash with "Could not set lock on file". Give the func worker its own
# isolated PORTAL_DATA_DIR; activities that need shared state call back
# into FastAPI via FASTAPI_WEBHOOK_URL (http://localhost:80).
FUNC_PORTAL_DATA_DIR="${FUNC_PORTAL_DATA_DIR:-/tmp/zava-func-portal}"
mkdir -p "${FUNC_PORTAL_DATA_DIR}"
(
  # function_app.py + host.json live at /app (the func project root).
  cd /app
  PYTHONPATH=/app PORTAL_DATA_DIR="${FUNC_PORTAL_DATA_DIR}" \
    exec func host start --port "${FUNC_PORT}" --no-build 2>&1 \
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
