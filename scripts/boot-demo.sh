#!/usr/bin/env bash
# Boots the full POC1 stack in one terminal. Ctrl-C stops everything.
#
# Low-laptop-load: Azurite via npm (no Docker), no file watchers,
# UI served from built bundle.
#
# Prereqs:
#   uv sync && npm install && npm run build
#   make funcvenv                           (Windows only)
#   cp local.settings.json.example local.settings.json
#   npm install -g azurite
#   gh auth login

set -u

cd "$(dirname "$0")/.."  # repo root
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

echo "==> azurite"
mkdir -p azurite-data
azurite --silent --location azurite-data \
  --blobHost 0.0.0.0 --queueHost 0.0.0.0 --tableHost 0.0.0.0 &
pids+=($!)

echo "    waiting for azurite ports..."
for i in $(seq 1 40); do
  b=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10000/devstoreaccount1 2>/dev/null || echo 000)
  q=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10001/devstoreaccount1 2>/dev/null || echo 000)
  t=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:10002/devstoreaccount1 2>/dev/null || echo 000)
  [ "$b" = "400" ] && [ "$q" = "400" ] && [ "$t" = "400" ] && break
  sleep 1
done
echo "    azurite ready; warming up 10s"
sleep 10

echo "==> mock MCPs (no watch)"
npm run demo:mcp &
pids+=($!)

echo "==> fastapi + fleet manager (no reload)"
uv run uvicorn api.server.main:app --port 3001 &
pids+=($!)

echo "==> vite preview (static)"
npm run demo:ui &
pids+=($!)

echo "==> portal preview (candidate UI)"
if [[ ! -d web/portal/dist ]]; then
  echo "    portal/dist missing — building..."
  npm run build:portal
fi
npm run demo:portal &
pids+=($!)

launch_func() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      NPM_BIN="$(cygpath -u "$APPDATA")/npm"
      source .funcvenv/Scripts/activate
      PATH="$NPM_BIN:$PATH" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd)" \
        func start --port 7071 &
      ;;
    *)
      source .venv/bin/activate
      PYTHONPATH="$(pwd)" func start --port 7071 &
      ;;
  esac
  FUNC_PID=$!
  pids+=($FUNC_PID)
}

echo "==> functions host (attempt 1)"
launch_func
# Poll 7071 for 30s
bound=0
for i in $(seq 1 15); do
  sleep 2
  if curl -s -o /dev/null http://localhost:7071/ 2>/dev/null; then bound=1; break; fi
done
if [ $bound -eq 0 ]; then
  echo "==> functions host didn't bind; restarting"
  kill -9 $FUNC_PID 2>/dev/null || true
  sleep 3
  launch_func
fi

cat <<EOF

All services should be up. Ports:
  UI:         http://localhost:5173
  Portal:     http://localhost:5174
  FastAPI:    http://localhost:3001
  Functions:  http://localhost:7071
  Azurite:    10000-10002

Inject:
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'

Ctrl-C to stop everything.
EOF

wait
