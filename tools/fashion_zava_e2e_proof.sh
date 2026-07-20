#!/usr/bin/env bash
set -euo pipefail

# Live, isolated end-to-end proof for the Fashion vertical. Built on the same
# real-stack harness the Telco proof uses (tools/lib/actor_world_proof_stack.sh):
# a fresh Azurite, the Fashion Azure Functions host, FastAPI with the Fashion
# actor world, and the real Control Plane + Blueprint Vite apps. Every verdict
# is derived from a live observation by tools/fashion_zava_e2e_proof.mjs — there
# are no self-certified PASS fields.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AZURITE_PORTS=(
  "${FASHION_PROOF_AZ_BLOB_PORT:-12000}"
  "${FASHION_PROOF_AZ_QUEUE_PORT:-12001}"
  "${FASHION_PROOF_AZ_TABLE_PORT:-12002}"
)
API_PORT="${FASHION_PROOF_API_PORT:-13301}"
FUNCTIONS_PORT="${FASHION_PROOF_FUNCTIONS_PORT:-17181}"
CONTROL_PLANE_PORT="${FASHION_PROOF_CONTROL_PLANE_PORT:-15373}"
BLUEPRINT_PORT="${FASHION_PROOF_BLUEPRINT_PORT:-15375}"
DATA_ROOT="${FASHION_PROOF_DATA_ROOT:-$ROOT/tmp/zava-fashion-proof-$(id -u)}"
OUT_DIR="${FASHION_PROOF_OUT_DIR:-$ROOT/proof}"
DRIVER="tools/fashion_zava_e2e_proof.mjs"
WORLD_MINUTES_PER_SECOND=60
MODE="full"

FASHION_ORCHESTRATORS=(
  InventoryRebalancingOrchestrator
  DemandSpikeResponseOrchestrator
  PromotionReadinessOrchestrator
  MarkdownGovernanceOrchestrator
  SupplierDelayRecoveryOrchestrator
  FulfilmentExceptionResolutionOrchestrator
  MarketplaceSellerExceptionOrchestrator
  ReturnsDispositionOrchestrator
)

if [[ "${1:-}" == "--print-config" ]]; then
  printf '{"api_port":%d,"azurite_ports":[%d,%d,%d],"blueprint_port":%d,"control_plane_port":%d,"data_root":"%s","driver":"%s","functions_port":%d,"out_dir":"%s","vertical":"fashion","world_minutes_per_second":%d}\n' \
    "$API_PORT" "${AZURITE_PORTS[0]}" "${AZURITE_PORTS[1]}" "${AZURITE_PORTS[2]}" \
    "$BLUEPRINT_PORT" "$CONTROL_PLANE_PORT" "$DATA_ROOT" "$DRIVER" \
    "$FUNCTIONS_PORT" "$OUT_DIR" "$WORLD_MINUTES_PER_SECOND"
  exit 0
fi
if [[ "${1:-}" == "--print-contract" ]]; then
  exec node "$ROOT/$DRIVER" --print-contract
fi
if [[ "${1:-}" == "--replay-only" ]]; then
  MODE="replay-only"
fi

# Both remaining modes (full and --replay-only) boot real processes and
# attribute their result to source_commit=$(git rev-parse HEAD) (full stamps
# it directly in the manifest; replay-only re-runs the driver against
# whatever is on disk right now). A dirty tree — tracked or untracked — means
# that attribution would be wrong, so fail fast here, before touching a
# single port or process. --print-config/--print-contract already exited
# above and stay usable on a dirty tree.
# shellcheck source=tools/lib/require_clean_source.sh
source "$ROOT/tools/lib/require_clean_source.sh"
require_clean_source "$ROOT" || exit 2

export ACTOR_PROOF_ROOT="$DATA_ROOT/run"
export ACTOR_PROOF_AZ_BLOB_PORT="${AZURITE_PORTS[0]}"
export ACTOR_PROOF_AZ_QUEUE_PORT="${AZURITE_PORTS[1]}"
export ACTOR_PROOF_AZ_TABLE_PORT="${AZURITE_PORTS[2]}"
export ACTOR_PROOF_FUNCTIONS_PORT="$FUNCTIONS_PORT"
export ACTOR_PROOF_API_PORT="$API_PORT"
export PROOF_WORLD="fashion"
export PROOF_SEED="42"
export PROOF_MPS="$WORLD_MINUTES_PER_SECOND"
export PROOF_ORCHESTRATOR_GREP="InventoryRebalancingOrchestrator"

# shellcheck source=tools/lib/actor_world_proof_stack.sh
source "$ROOT/tools/lib/actor_world_proof_stack.sh"
cd "$ROOT"

CONTROL_PLANE_LOG="$COMPOSE_DIR/fashion-control-plane.log"
BLUEPRINT_LOG="$COMPOSE_DIR/fashion-blueprint.log"
REPLAY_API_LOG="$COMPOSE_DIR/fashion-replay-api.log"
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
PORTS_RELEASED="unknown"

cleanup() {
  [[ -n "$CLEANED" ]] && return 0
  CLEANED=1
  log "tearing down isolated Fashion proof"
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
  if [[ "$busy" -eq 0 ]]; then
    log "all proof ports released (${ALL_PORTS[*]})"
    PORTS_RELEASED="yes"
  else
    PORTS_RELEASED="no"
  fi
  return "$busy"
}
trap cleanup EXIT INT TERM

wait_http() {
  local url="$1" label="$2" pid="$3" log_file="$4" attempts="${5:-60}" _
  for _ in $(seq 1 "$attempts"); do
    if ! kill -0 "$pid" 2>/dev/null; then
      err "$label exited early"; tail -n 40 "$log_file" >&2 || true; return 1
    fi
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      log "$label ready (pid $pid)"; return 0
    fi
    sleep 1
  done
  err "$label did not become ready: $url"; tail -n 40 "$log_file" >&2 || true; return 1
}

wait_port_clear() {
  local port="$1" label="$2" _
  for _ in $(seq 1 40); do
    if ! port_listening "$port"; then log "$label stopped (port $port clear)"; return 0; fi
    sleep 0.5
  done
  err "$label still reachable on port $port"; return 1
}

assemble_manifest() {
  local source_commit teardown_status
  source_commit="$(git -C "$ROOT" rev-parse HEAD)"
  teardown_status="$1"
  SOURCE_COMMIT="$source_commit" \
  TEARDOWN_STATUS="$teardown_status" \
  PORTS_RELEASED="$PORTS_RELEASED" \
  PROOF_OUT_DIR="$OUT_DIR" \
  ALL_PORTS="${ALL_PORTS[*]}" \
    uv run --frozen --no-sync python "$ROOT/tools/fashion_proof_manifest.py"
}

# --- replay-only mode ------------------------------------------------------
if [[ "$MODE" == "replay-only" ]]; then
  for required in curl lsof node uv; do
    command -v "$required" >/dev/null || { err "missing required command: $required"; exit 2; }
  done
  preflight_ports "$API_PORT" "$FUNCTIONS_PORT" "$BLUEPRINT_PORT"
  mkdir -p "$OUT_DIR/recordings" "$OUT_DIR/logs" "$DATA_ROOT"
  export BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings"

  ( cd "$ROOT" \
      && exec env -u ZAVA_WORLD -u FUNCTIONS_HOST \
        ZAVA_VERTICAL=fashion ZAVA_BLUEPRINT_REPLAY_ONLY=1 \
        PORTAL_DATA_DIR="$DATA_ROOT/replay-portal" ENTITY_PLANE_ENABLED=0 \
        SIMULATOR_RAMP_ENABLED=0 BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings" \
        uv run --frozen --no-sync uvicorn api.server.main:app \
          --host 127.0.0.1 --port "$API_PORT" ) \
    >"$REPLAY_API_LOG" 2>&1 &
  API_PID=$!
  wait_http "http://127.0.0.1:$API_PORT/healthz" "replay FastAPI" "$API_PID" "$REPLAY_API_LOG"

  ( cd "$ROOT/web/blueprint" \
      && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
        "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$BLUEPRINT_PORT" --strictPort ) \
    >"$BLUEPRINT_LOG" 2>&1 &
  BLUEPRINT_PID=$!
  wait_http "http://127.0.0.1:$BLUEPRINT_PORT/?view=constellation" "Blueprint replay" "$BLUEPRINT_PID" "$BLUEPRINT_LOG"

  set +e
  BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
  WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
  FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT" \
  PROOF_OUT_DIR="$OUT_DIR" \
    node "$DRIVER" --replay
  rc=$?
  set -e
  mkdir -p "$OUT_DIR/logs"; cp "$REPLAY_API_LOG" "$BLUEPRINT_LOG" "$OUT_DIR/logs/" 2>/dev/null || true
  if ! cleanup; then rc=9; fi
  trap - EXIT INT TERM
  exit "$rc"
fi

# --- full live proof -------------------------------------------------------
for required in azurite curl func lsof node uv; do
  command -v "$required" >/dev/null || { err "missing required command: $required"; exit 2; }
done

preflight_ports "${ALL_PORTS[@]}"
rm -rf "$DATA_ROOT" "$OUT_DIR"
mkdir -p "$DATA_ROOT/portal" "$DATA_ROOT/memory" "$OUT_DIR/recordings" "$OUT_DIR/logs"

export PORTAL_DATA_DIR="$DATA_ROOT/portal"
export ENTITY_GRAPH_PATH="$DATA_ROOT/entity_graph.kuzu"
export MEMORY_FALLBACK_DIR="$DATA_ROOT/memory"
export BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings"
export ZAVA_VERTICAL="fashion"
export SIMULATOR_RAMP_ENABLED="0"
export DREAM_PASS_DEMO_CADENCE_SECONDS="0"
export ENTITY_PLANE_ENABLED="1"
export MAX_OBSERVATORY_EVENTS_PER_SEC="10000"
export DURABLE_EVENT_SECRET="fashion-proof-local-isolated"
export FASTAPI_WEBHOOK_URL="http://127.0.0.1:$API_PORT/internal/durable-event"
export CORS_ALLOWED_ORIGINS="http://127.0.0.1:$CONTROL_PLANE_PORT,http://127.0.0.1:$BLUEPRINT_PORT,http://127.0.0.1:$API_PORT"
export AzureWebJobsStorage="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:${AZURITE_PORTS[0]}/devstoreaccount1;QueueEndpoint=http://127.0.0.1:${AZURITE_PORTS[1]}/devstoreaccount1;TableEndpoint=http://127.0.0.1:${AZURITE_PORTS[2]}/devstoreaccount1;"

start_azurite
start_functions_host
for orchestrator in "${FASHION_ORCHESTRATORS[@]}"; do
  grep -q "$orchestrator" "$FUNC_LOG" || { err "Functions host did not index $orchestrator"; exit 4; }
done
log "all 8 Fashion orchestrators indexed"
start_fastapi

log "starting Control Plane (:$CONTROL_PLANE_PORT)"
( exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
    VITE_BLUEPRINT_URL="http://127.0.0.1:$BLUEPRINT_PORT" \
    "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$CONTROL_PLANE_PORT" --strictPort ) \
  >"$CONTROL_PLANE_LOG" 2>&1 &
CONTROL_PLANE_PID=$!
wait_http "http://127.0.0.1:$CONTROL_PLANE_PORT/world" "Control Plane" "$CONTROL_PLANE_PID" "$CONTROL_PLANE_LOG"

log "starting Blueprint (:$BLUEPRINT_PORT)"
( cd "$ROOT/web/blueprint" \
    && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
      "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$BLUEPRINT_PORT" --strictPort ) \
  >"$BLUEPRINT_LOG" 2>&1 &
BLUEPRINT_PID=$!
wait_http "http://127.0.0.1:$BLUEPRINT_PORT/?view=constellation" "Blueprint" "$BLUEPRINT_PID" "$BLUEPRINT_LOG"

DRIVER_ENV=(
  "CONTROL_PLANE_BASE=http://127.0.0.1:$CONTROL_PLANE_PORT"
  "BLUEPRINT_BASE=http://127.0.0.1:$BLUEPRINT_PORT"
  "WORLD_API_BASE=http://127.0.0.1:$API_PORT"
  "FUNCTIONS_HOST=http://127.0.0.1:$FUNCTIONS_PORT"
  "PROOF_OUT_DIR=$OUT_DIR"
)

log "running live Fashion Playwright proof (forward chain, 8 workflows)"
set +e
env "${DRIVER_ENV[@]}" node "$DRIVER"
rc=$?
set -e

# --- genuine Functions-disabled negative probe (VERTICAL-PROOF §3a) --------
if [[ "$rc" -eq 0 ]]; then
  log "probe: stopping Functions host for the negative probe"
  kill_tree "$FUNC_PID" "functions-host"; FUNC_PID=""
  wait_port_clear "$FUNCTIONS_PORT" "Functions host"
  set +e
  env "${DRIVER_ENV[@]}" node "$DRIVER" --probe-functions-disabled
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    log "probe: restarting Functions host and confirming recovery"
    start_functions_host
    if grep -q "InventoryRebalancingOrchestrator" "$FUNC_LOG"; then
      # Drives a fresh returns-disposition trigger (runRecoveryProbe in the
      # driver) and, reusing the same waitForNewCompletedWorkflow() the
      # forward chain uses (including its HITL auto-resolution), requires
      # *that exact new* case/workflow to reach completed. Never satisfied by
      # a workflow the earlier live forward proof already completed: the
      # driver captures known workflow ids before triggering, requires the
      # POST to return ok:true with a case_id, and fails closed otherwise.
      set +e
      env "${DRIVER_ENV[@]}" node "$DRIVER" --probe-recovery
      rc=$?
      set -e
      if [[ "$rc" -eq 0 ]]; then
        log "probe: recovery confirmed (new returns-disposition workflow completed after restart)"
      else
        err "recovery: newly triggered returns-disposition workflow did not complete after Functions restart"
      fi
    else
      err "recovery: orchestrator not indexed after restart"; rc=4
    fi
  fi
fi

mkdir -p "$OUT_DIR/logs"
cp "$AZ_LOG" "$FUNC_LOG" "$API_LOG" "$CONTROL_PLANE_LOG" "$BLUEPRINT_LOG" "$OUT_DIR/logs/" 2>/dev/null || true

# --- actor-world-disabled replay (VERTICAL-PROOF §3b, Telco-consistent) -----
if [[ "$rc" -eq 0 ]]; then
  log "validating recorded replay with Functions host + actor world disabled"
  kill_tree "$CONTROL_PLANE_PID" "control-plane"; CONTROL_PLANE_PID=""
  kill_tree "$API_PID" "fastapi"; API_PID=""
  kill_tree "$FUNC_PID" "functions-host"; FUNC_PID=""
  kill_tree "$AZ_PID" "azurite"; AZ_PID=""
  wait_port_clear "$API_PORT" "live FastAPI"
  wait_port_clear "$FUNCTIONS_PORT" "Functions host"
  for port in "${AZURITE_PORTS[@]}"; do wait_port_clear "$port" "Azurite"; done

  ( cd "$ROOT" \
      && exec env -u ZAVA_WORLD -u FUNCTIONS_HOST \
        ZAVA_VERTICAL=fashion ZAVA_BLUEPRINT_REPLAY_ONLY=1 \
        PORTAL_DATA_DIR="$DATA_ROOT/replay-portal" ENTITY_PLANE_ENABLED=0 \
        SIMULATOR_RAMP_ENABLED=0 BLUEPRINT_RECORDINGS_DIR="$OUT_DIR/recordings" \
        uv run --frozen --no-sync uvicorn api.server.main:app \
          --host 127.0.0.1 --port "$API_PORT" ) \
    >"$REPLAY_API_LOG" 2>&1 &
  API_PID=$!
  wait_http "http://127.0.0.1:$API_PORT/healthz" "replay FastAPI" "$API_PID" "$REPLAY_API_LOG"

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

teardown_status="PASS"
if ! cleanup; then rc=9; teardown_status="FAIL"; fi
[[ "$PORTS_RELEASED" == "yes" ]] || teardown_status="FAIL"
trap - EXIT INT TERM

# Assemble the manifest from observed evidence; it is PASS only if every phase
# and the teardown passed. assemble_manifest exits non-zero on a FAIL manifest.
if ! assemble_manifest "$teardown_status"; then
  err "FASHION ZAVA E2E PROOF FAILED (manifest status FAIL)"
  exit 1
fi
if [[ "$rc" -ne 0 ]]; then
  err "FASHION ZAVA E2E PROOF FAILED (exit $rc)"
  exit "$rc"
fi
log "FASHION ZAVA E2E PROOF PASSED"
log "evidence: $OUT_DIR (manifest.json)"
exit 0
