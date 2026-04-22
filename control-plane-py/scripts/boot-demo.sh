#!/usr/bin/env bash
# Boots the full POC1 stack in one terminal. Ctrl-C stops everything.
#
# Low-laptop-load mode: Azurite runs natively via npm (no Docker Desktop),
# uvicorn runs without --reload, mocks run without tsx watch, the UI is
# served from the built bundle via `vite preview` (no HMR / TS compiler
# loop). Expect ~70% less sustained CPU than the old dev-mode boot.
#
# Prereqs (run once):
#   uv sync
#   make funcvenv                         (Windows only)
#   cp local.settings.json.example local.settings.json
#   (cd ../control-plane && npm install && npm run build)
#   npm install -g azurite                (if not already)
#   gh auth login

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
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

echo "==> azurite (native npm, no docker)"
mkdir -p azurite-data
( azurite --silent --location azurite-data \
    --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 ) &
pids+=($!)

echo "    waiting for azurite (blob/queue/table)..."
for i in $(seq 1 40); do
  b=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10000/devstoreaccount1 2>/dev/null || echo 000)
  q=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10001/devstoreaccount1 2>/dev/null || echo 000)
  t=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10002/devstoreaccount1 2>/dev/null || echo 000)
  if [ "$b" = "400" ] && [ "$q" = "400" ] && [ "$t" = "400" ]; then
    echo "    azurite ready; warming up (5s)"
    sleep 5
    break
  fi
  sleep 1
done

echo "==> mock MCPs (no watch)"
( cd ../control-plane && npm run demo:mcp ) &
pids+=($!)

start_func() {
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
  echo $!
}

func_bound() {
  curl -s -o /dev/null -w "%{http_code}" http://localhost:7071/ 2>/dev/null | grep -qE '^(2|3|4|5)' && return 0 || return 1
}

echo "==> functions host (attempt 1)"
FPID=$(start_func)
pids+=($FPID)
# Watchdog: func often dies on cold-start with "Value cannot be null (provider)".
# If 7071 isn't bound within 30s, retry once — second attempt reliably succeeds.
for i in $(seq 1 15); do
  sleep 2
  if func_bound; then echo "    func bound"; break; fi
done
if ! func_bound; then
  echo "==> functions host died on first attempt, retrying..."
  kill -9 $FPID 2>/dev/null || true
  sleep 2
  FPID=$(start_func)
  pids+=($FPID)
fi

echo "==> fastapi + fleet manager (no reload)"
uv run uvicorn src.server.main:app --port 3001 &
pids+=($!)

echo "==> vite ui (static preview, no HMR)"
( cd ../control-plane && npm run demo:ui ) &
pids+=($!)

cat <<EOF

All services starting. Ports:
  UI:         http://localhost:5173
  FastAPI:    http://localhost:3001  (docs at /docs)
  Functions:  http://localhost:7071
  Azurite:    10000-10002

Takes ~60s for the simulator to ramp workflows.

Inject demo scenarios via the DevPanel (top-right on Fleet Dashboard, dev build only)
or via curl:
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-hitl"}'

You can stop Docker Desktop entirely; this script no longer needs it.

Ctrl-C to stop everything.
EOF

wait
