#!/usr/bin/env bash
# Boots the full POC1 stack in one terminal.
# Ctrl-C stops everything.
#
# Prereqs (run once):
#   uv sync
#   make funcvenv
#   cp local.settings.json.example local.settings.json
#   (cd ../control-plane && npm install)
#   gh auth login   # must have Copilot
set -eu

cd "$(dirname "$0")/.."  # control-plane-py/

[[ -f .env ]] || cp .env.example .env

pids=()
cleanup() {
  echo ""
  echo "stopping services..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  docker compose stop azurite >/dev/null 2>&1 || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> azurite"
docker compose up -d azurite

# Wait for Azurite to actually accept connections on 10000 before starting
# func — otherwise the host aborts with "Value cannot be null (provider)".
echo "    waiting for azurite on 10000..."
for i in $(seq 1 30); do
  if powershell.exe -Command "(Test-NetConnection -ComputerName localhost -Port 10000 -WarningAction SilentlyContinue -InformationLevel Quiet)" 2>/dev/null | grep -q True; then
    echo "    azurite ready"
    break
  fi
  sleep 1
done

echo "==> mock MCPs"
( cd ../control-plane && npm run dev:mcp ) &
pids+=($!)

echo "==> functions host"
# 1. `source activate` sets VIRTUAL_ENV so func's Python worker uses .funcvenv
#    (with azure-functions-durable etc.) instead of the system Python 3.11.
# 2. Prepend npm's bin so `func` resolves to 4.9.0 (npm) not 4.0.5455 (MSI).
#    The MSI version ships .NET 6 which can't load the Durable extension
#    bundle v4 that requires .NET 8.
#    cygpath converts Windows-style $APPDATA to MSYS Unix style so PATH works.
# 3. PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 side-steps a StringBuilder overflow
#    in func 4.9.0's Python version probe on Windows.
NPM_BIN="$(cygpath -u "$APPDATA")/npm"
( source .funcvenv/Scripts/activate \
    && PATH="$NPM_BIN:$PATH" \
       PYTHONUTF8=1 \
       PYTHONIOENCODING=utf-8 \
       PYTHONPATH="$(pwd)" \
       func start --port 7071 ) &
pids+=($!)

echo "==> fastapi + fleet manager"
uv run uvicorn src.server.main:app --port 3001 --reload &
pids+=($!)

echo "==> vite ui"
( cd ../control-plane && npm run dev:client ) &
pids+=($!)

cat <<EOF

All services starting. Ports:
  UI:         http://localhost:5173
  FastAPI:    http://localhost:3001  (docs at /docs)
  Functions:  http://localhost:7071
  Azurite:    10000-10002

Takes ~60s for the simulator to ramp workflows.

Inject demo scenarios from the DevPanel (top-right on Fleet Dashboard, dev build only)
or via curl:
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-hitl"}'

Ctrl-C to stop everything.
EOF

wait
