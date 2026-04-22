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

# Wait for Azurite's Blob, Queue, Table services to respond. Port-bind alone
# is not enough — func's Durable Task extension aborts with "Value cannot be
# null (provider)" if Azurite is bound but not yet serving. Probe each service
# with a curl that expects HTTP 400 (missing auth). Also add a small buffer.
echo "    waiting for azurite (blob/queue/table)..."
for i in $(seq 1 40); do
  b=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10000/devstoreaccount1 2>/dev/null)
  q=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10001/devstoreaccount1 2>/dev/null)
  t=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10002/devstoreaccount1 2>/dev/null)
  if [ "$b" = "400" ] && [ "$q" = "400" ] && [ "$t" = "400" ]; then
    echo "    azurite ready (blob=$b queue=$q table=$t)"
    sleep 2
    break
  fi
  sleep 1
done

echo "==> mock MCPs"
( cd ../control-plane && npm run dev:mcp ) &
pids+=($!)

echo "==> functions host"
# Branch by OS. On Windows (git-bash/MSYS) we need the .funcvenv dance + the
# npm-vs-MSI func shim + PYTHONUTF8 workaround. On Linux (devcontainer /
# Codespaces) the uv-created `.venv` is Python 3.11, func@4.9.0 is on PATH
# from post-create, and PYTHONUTF8 is already exported.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    NPM_BIN="$(cygpath -u "$APPDATA")/npm"
    ( source .funcvenv/Scripts/activate \
        && PATH="$NPM_BIN:$PATH" \
           PYTHONUTF8=1 \
           PYTHONIOENCODING=utf-8 \
           PYTHONPATH="$(pwd)" \
           func start --port 7071 ) &
    ;;
  *)
    ( source .venv/bin/activate \
        && PYTHONPATH="$(pwd)" \
           func start --port 7071 ) &
    ;;
esac
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
