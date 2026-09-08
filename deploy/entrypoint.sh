#!/usr/bin/env bash
# Container entrypoint: supervise Azure Functions (:7071) and uvicorn (:80).
# In live mode either service exiting must stop the whole container.
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

# Kuzu (entity graph) holds an exclusive file lock per process. uvicorn
# opens data/portal/entity_graph.kuzu first, so the func worker — which
# imports the same substrate module-tree via function_app.py — would
# crash with "Could not set lock on file". Give the func worker its own
# isolated PORTAL_DATA_DIR; activities that need shared state call back
# into FastAPI via FASTAPI_WEBHOOK_URL (http://localhost:80).
FUNC_PORTAL_DATA_DIR="${FUNC_PORTAL_DATA_DIR:-/app/data/functions}"
# .NET cannot resolve LocalApplicationData when its directory is absent.
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME:-/root}/.local/share}"
mkdir -p "${FUNC_PORTAL_DATA_DIR}" "${XDG_DATA_HOME}"

FUNC_PID=""
API_PID=""
cleanup() {
  trap - EXIT TERM INT
  echo "[entrypoint] stopping Functions and API"
  local pid deadline
  for pid in "${FUNC_PID}" "${API_PID}"; do
    [[ -z "${pid}" ]] || kill -TERM -- "-${pid}" 2>/dev/null || true
  done
  deadline=$((SECONDS + 5))
  while (( SECONDS < deadline )); do
    if ! kill -0 -- "-${FUNC_PID}" 2>/dev/null \
      && ! kill -0 -- "-${API_PID}" 2>/dev/null; then
      break
    fi
    sleep 0.1
  done
  for pid in "${FUNC_PID}" "${API_PID}"; do
    [[ -z "${pid}" ]] || kill -KILL -- "-${pid}" 2>/dev/null || true
  done
  wait "${FUNC_PID}" 2>/dev/null || true
  wait "${API_PID}" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

# Separate owned process groups let cleanup also stop Functions' Python worker.
# Avoid a logging pipeline: its PID would belong to a shell, not the host.
set -m
echo "[entrypoint] starting Azure Functions host on :${FUNC_PORT}"
(
  cd /app
  # QEMU's aliased executable mappings can break .NET dynamic invocation.
  # Opt in only for local emulation; native deployments retain .NET's W^X.
  if [[ "${ZAVA_FUNCTIONS_QEMU_COMPAT:-0}" == "1" ]]; then
    export DOTNET_EnableWriteXorExecute="${DOTNET_EnableWriteXorExecute:-0}"
    echo "[entrypoint] using opt-in Functions QEMU compatibility"
  fi
  export PYTHONPATH=/app PORTAL_DATA_DIR="${FUNC_PORTAL_DATA_DIR}"
  exec func host start --port "${FUNC_PORT}" --no-build
) &
FUNC_PID=$!

echo "[entrypoint] starting uvicorn on :${PORT}"
uvicorn api.server.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 &
API_PID=$!

# Polling also works with macOS Bash 3.2 (unlike wait -n).
while kill -0 "${FUNC_PID}" 2>/dev/null && kill -0 "${API_PID}" 2>/dev/null; do
  sleep 1
done

status=0
if ! kill -0 "${FUNC_PID}" 2>/dev/null; then
  wait "${FUNC_PID}" || status=$?
  echo "[entrypoint] Functions exited (status=${status})"
else
  wait "${API_PID}" || status=$?
  echo "[entrypoint] API exited (status=${status})"
fi
# A clean but unexpected child exit is still a failed live container.
if (( status == 0 )); then
  status=1
fi
exit "${status}"
