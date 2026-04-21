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

echo "==> mock MCPs"
( cd ../control-plane && npm run dev:mcp ) &
pids+=($!)

echo "==> functions host"
( PATH="$(pwd)/.funcvenv/Scripts:$PATH" PYTHONPATH="$(pwd)" func start --port 7071 ) &
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
