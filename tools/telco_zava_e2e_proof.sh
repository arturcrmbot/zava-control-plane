#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AZURITE_PORTS=(
  "${TELCO_PROOF_AZ_BLOB_PORT:-11000}"
  "${TELCO_PROOF_AZ_QUEUE_PORT:-11001}"
  "${TELCO_PROOF_AZ_TABLE_PORT:-11002}"
)
API_PORT="${TELCO_PROOF_API_PORT:-13101}"
FUNCTIONS_PORT="${TELCO_PROOF_FUNCTIONS_PORT:-17171}"
CONTROL_PLANE_PORT="${TELCO_PROOF_CONTROL_PLANE_PORT:-15273}"
BLUEPRINT_PORT="${TELCO_PROOF_BLUEPRINT_PORT:-15275}"
DATA_ROOT="${TELCO_PROOF_DATA_ROOT:-/tmp/zava-telco-proof-$(id -u)}"
DRIVER="tools/telco_zava_e2e_proof.mjs"
WORLD_MINUTES_PER_SECOND=10

if [[ "${1:-}" == "--print-config" ]]; then
  printf '{"api_port":%d,"azurite_ports":[%d,%d,%d],"blueprint_port":%d,"control_plane_port":%d,"data_root":"%s","driver":"%s","functions_port":%d,"vertical":"telco","world_minutes_per_second":%d}\n' \
    "$API_PORT" "${AZURITE_PORTS[0]}" "${AZURITE_PORTS[1]}" "${AZURITE_PORTS[2]}" \
    "$BLUEPRINT_PORT" "$CONTROL_PLANE_PORT" "$DATA_ROOT" "$DRIVER" \
    "$FUNCTIONS_PORT" "$WORLD_MINUTES_PER_SECOND"
  exit 0
fi

export ACTOR_PROOF_ROOT="$DATA_ROOT/run"
export ACTOR_PROOF_AZ_BLOB_PORT="${AZURITE_PORTS[0]}"
export ACTOR_PROOF_AZ_QUEUE_PORT="${AZURITE_PORTS[1]}"
export ACTOR_PROOF_AZ_TABLE_PORT="${AZURITE_PORTS[2]}"
export ACTOR_PROOF_FUNCTIONS_PORT="$FUNCTIONS_PORT"
export ACTOR_PROOF_API_PORT="$API_PORT"
export PROOF_WORLD="telco"
export PROOF_SEED="42"
export PROOF_MPS="$WORLD_MINUTES_PER_SECOND"
export PROOF_ORCHESTRATOR_GREP="ProactiveCustomerCareOrchestrator"

# shellcheck source=tools/lib/actor_world_proof_stack.sh
source "$ROOT/tools/lib/actor_world_proof_stack.sh"
cd "$ROOT"

OUT_DIR="${TELCO_PROOF_OUT_DIR:-$ROOT/tmp/telco-zava-e2e-proof}"
CONTROL_PLANE_LOG="$COMPOSE_DIR/control-plane.log"
BLUEPRINT_LOG="$COMPOSE_DIR/blueprint.log"
REPLAY_API_LOG="$COMPOSE_DIR/replay-api.log"
CONTROL_PLANE_PID=""
BLUEPRINT_PID=""
CLEANED=""
ALL_PORTS=(
  "${AZURITE_PORTS[@]}"
  "$API_PORT"
  "$FUNCTIONS_PORT"
  "$CONTROL_PLANE_PORT"
  "$BLUEPRINT_PORT"
)

cleanup() {
  [[ -n "$CLEANED" ]] && return 0
  CLEANED=1
  log "tearing down isolated Telco proof"
  kill_tree "$CONTROL_PLANE_PID" "control-plane"
  kill_tree "$BLUEPRINT_PID" "blueprint"
  teardown_stack
  sleep 1
  local busy=0 port
  for port in "${ALL_PORTS[@]}"; do
    if port_listening "$port"; then
      err "port $port still listening after teardown"
      busy=1
    fi
  done
  [[ "$busy" -eq 0 ]] && log "all proof ports released (${ALL_PORTS[*]})"
  return "$busy"
}
trap cleanup EXIT INT TERM

wait_http() {
  local url="$1" label="$2" pid="$3" log_file="$4" attempts="${5:-60}"
  local _
  for _ in $(seq 1 "$attempts"); do
    if ! kill -0 "$pid" 2>/dev/null; then
      err "$label exited early"
      tail -n 40 "$log_file" >&2 || true
      return 1
    fi
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      log "$label ready (pid $pid)"
      return 0
    fi
    sleep 1
  done
  err "$label did not become ready: $url"
  tail -n 40 "$log_file" >&2 || true
  return 1
}

wait_port_clear() {
  local port="$1" label="$2" _
  for _ in $(seq 1 40); do
    if ! port_listening "$port"; then
      log "$label stopped (port $port clear)"
      return 0
    fi
    sleep 0.5
  done
  err "$label still reachable on port $port"
  return 1
}

for required in azurite curl func lsof node uv; do
  command -v "$required" >/dev/null || {
    err "missing required command: $required"
    exit 2
  }
done

preflight_ports "${ALL_PORTS[@]}"
rm -rf "$DATA_ROOT" "$OUT_DIR"
mkdir -p "$DATA_ROOT/portal" "$DATA_ROOT/memory" "$OUT_DIR/recordings"

export PORTAL_DATA_DIR="$DATA_ROOT/portal"
export ENTITY_GRAPH_PATH="$DATA_ROOT/entity_graph.kuzu"
export MEMORY_FALLBACK_DIR="$DATA_ROOT/memory"
export BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings"
export ZAVA_VERTICAL="telco"
export SIMULATOR_RAMP_ENABLED="0"
export DREAM_PASS_DEMO_CADENCE_SECONDS="0"
export ENTITY_PLANE_ENABLED="1"
export AGT_ENFORCE="1"
export DURABLE_EVENT_SECRET="telco-proof-local-isolated"
export FASTAPI_WEBHOOK_URL="http://127.0.0.1:$API_PORT/internal/durable-event"
export CORS_ALLOWED_ORIGINS="http://127.0.0.1:$CONTROL_PLANE_PORT,http://127.0.0.1:$BLUEPRINT_PORT,http://127.0.0.1:$API_PORT"
export AzureWebJobsStorage="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:${AZURITE_PORTS[0]}/devstoreaccount1;QueueEndpoint=http://127.0.0.1:${AZURITE_PORTS[1]}/devstoreaccount1;TableEndpoint=http://127.0.0.1:${AZURITE_PORTS[2]}/devstoreaccount1;"

start_azurite
start_functions_host
for orchestrator in NetworkIncidentOrchestrator ProactiveCustomerCareOrchestrator OrderToActivateOrchestrator; do
  grep -q "$orchestrator" "$FUNC_LOG" || {
    err "Functions host did not index $orchestrator"
    exit 4
  }
done
start_fastapi

log "starting Control Plane (:$CONTROL_PLANE_PORT)"
( exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
    VITE_BLUEPRINT_URL="http://127.0.0.1:$BLUEPRINT_PORT" \
    "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 \
    --port "$CONTROL_PLANE_PORT" --strictPort ) \
  >"$CONTROL_PLANE_LOG" 2>&1 &
CONTROL_PLANE_PID=$!
wait_http "http://127.0.0.1:$CONTROL_PLANE_PORT/world" \
  "Control Plane" "$CONTROL_PLANE_PID" "$CONTROL_PLANE_LOG"

log "starting Blueprint (:$BLUEPRINT_PORT)"
( cd "$ROOT/web/blueprint" \
    && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
      "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 \
      --port "$BLUEPRINT_PORT" --strictPort ) \
  >"$BLUEPRINT_LOG" 2>&1 &
BLUEPRINT_PID=$!
wait_http "http://127.0.0.1:$BLUEPRINT_PORT/?view=constellation" \
  "Blueprint" "$BLUEPRINT_PID" "$BLUEPRINT_LOG"

log "running live Telco Playwright proof"
set +e
CONTROL_PLANE_BASE="http://127.0.0.1:$CONTROL_PLANE_PORT" \
BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT" \
PROOF_OUT_DIR="$OUT_DIR" \
  node "$DRIVER"
rc=$?
set -e

mkdir -p "$OUT_DIR/logs"
cp "$AZ_LOG" "$FUNC_LOG" "$API_LOG" "$CONTROL_PLANE_LOG" "$BLUEPRINT_LOG" \
  "$OUT_DIR/logs/" 2>/dev/null || true

if [[ "$rc" -eq 0 ]]; then
  log "validating recorded replay without Functions host"
  kill_tree "$CONTROL_PLANE_PID" "control-plane"
  CONTROL_PLANE_PID=""
  kill_tree "$API_PID" "fastapi"
  API_PID=""
  kill_tree "$FUNC_PID" "functions-host"
  FUNC_PID=""
  kill_tree "$AZ_PID" "azurite"
  AZ_PID=""
  wait_port_clear "$API_PORT" "live FastAPI"
  wait_port_clear "$FUNCTIONS_PORT" "Functions host"
  for port in "${AZURITE_PORTS[@]}"; do
    wait_port_clear "$port" "Azurite"
  done

  ( cd "$ROOT" \
      && exec env -u ZAVA_WORLD -u FUNCTIONS_HOST \
        ZAVA_VERTICAL=telco \
        ZAVA_BLUEPRINT_REPLAY_ONLY=1 \
        PORTAL_DATA_DIR="$DATA_ROOT/replay-portal" \
        ENTITY_PLANE_ENABLED=0 \
        SIMULATOR_RAMP_ENABLED=0 \
        BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings" \
        uv run --frozen --no-sync uvicorn api.server.main:app \
          --host 127.0.0.1 --port "$API_PORT" ) \
    >"$REPLAY_API_LOG" 2>&1 &
  API_PID=$!
  wait_http "http://127.0.0.1:$API_PORT/healthz" \
    "replay FastAPI" "$API_PID" "$REPLAY_API_LOG"

  set +e
  BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
  WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
  FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT" \
  PROOF_OUT_DIR="$OUT_DIR" \
    node "$DRIVER" --replay
  rc=$?
  set -e
  cp "$REPLAY_API_LOG" "$OUT_DIR/logs/" 2>/dev/null || true
fi

if ! cleanup; then
  rc=9
fi
trap - EXIT INT TERM

if [[ "$rc" -eq 0 ]]; then
  log "TELCO ZAVA E2E PROOF PASSED"
  log "evidence: $OUT_DIR"
else
  err "TELCO ZAVA E2E PROOF FAILED (exit $rc)"
fi
exit "$rc"
