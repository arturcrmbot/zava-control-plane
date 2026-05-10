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
# Phase 3 TASK-025a of plan/feature-agent-governance-toolkit-1.md:
# the authority-mcp Node mock (port 4108) is no longer started by
# default. Resolve / check are served in-process by the governance
# kernel (governance.kernel().resolve_approver / check_authority).
# Set BOOT_DEMO_WITH_AUTHORITY_MOCK=1 (or use `make boot-demo-with-authority-mock`)
# to bring it up alongside for parity testing or for the engagement-POC
# swap-in dry run.
if [[ "${BOOT_DEMO_WITH_AUTHORITY_MOCK:-0}" == "1" ]]; then
  echo "    (with authority-mcp on :4108 — set AUTHORITY_MCP_URL to use it)"
  npm run demo:mcp:with-authority &
else
  npm run demo:mcp &
fi
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

echo "==> blueprint preview (Constellation)"
if [[ ! -d web/blueprint/dist ]]; then
  echo "    blueprint/dist missing — building..."
  npm run build:blueprint
fi
npm run demo:blueprint &
pids+=($!)

launch_func() {
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      NPM_BIN="$(cygpath -u "$APPDATA")/npm"
      source .funcvenv/Scripts/activate
      ENTITY_PLANE_ENABLED=0 PATH="$NPM_BIN:$PATH" PYTHONUTF8=1 PYTHONIOENCODING=utf-8 PYTHONPATH="$(pwd)" \
        func start --port 7071 &
      ;;
    *)
      source .venv/bin/activate
      ENTITY_PLANE_ENABLED=0 PYTHONPATH="$(pwd)" func start --port 7071 &
      ;;
  esac
  FUNC_PID=$!
  pids+=($FUNC_PID)
}

if [[ "${BOOT_DEMO_SKIP_FUNC:-0}" == "1" ]]; then
  echo "==> functions host SKIPPED (BOOT_DEMO_SKIP_FUNC=1) — no Durable orchestrators on :7071"
else
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
fi

cat <<EOF

All services should be up. Ports:
  UI:           http://localhost:5173
  Portal:       http://localhost:5174
  Constellation: http://localhost:5175
  FastAPI:      http://localhost:3001
  Functions:    http://localhost:7071
  Azurite:      10000-10002

Inject:
  curl -X POST http://localhost:3001/api/simulator/inject -H "Content-Type: application/json" -d '{"scenario":"demo-fail"}'

Ctrl-C to stop everything.
EOF

wait
