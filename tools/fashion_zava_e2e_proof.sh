#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

AZURITE_PORTS=(
  "${FASHION_PROOF_AZ_BLOB_PORT:-12000}"
  "${FASHION_PROOF_AZ_QUEUE_PORT:-12001}"
  "${FASHION_PROOF_AZ_TABLE_PORT:-12002}"
)
FUNCTIONS_PORT="${FASHION_PROOF_FUNCTIONS_PORT:-17271}"
API_PORT="${FASHION_PROOF_API_PORT:-13201}"
CONTROL_PLANE_PORT="${FASHION_PROOF_CONTROL_PLANE_PORT:-15373}"
BLUEPRINT_PORT="${FASHION_PROOF_BLUEPRINT_PORT:-15375}"
PROOF_DIR="$ROOT/proof"
RUNTIME_DIR="$PROOF_DIR/runtime"
DRIVER="tools/fashion_zava_e2e_proof.mjs"
WORLD_MINUTES_PER_SECOND=6
DIRTY_DEVELOPMENT=0
MODE="full"

print_config() {
  printf '{"driver":"%s","ports":{"api":%d,"azurite":[%d,%d,%d],"blueprint":%d,"control_plane":%d,"functions":%d},"proof_dir":"proof","runtime_dir":"proof/runtime","seed":42,"vertical":"fashion","world_minutes_per_second":%d}\n' \
    "$DRIVER" "$API_PORT" "${AZURITE_PORTS[0]}" "${AZURITE_PORTS[1]}" \
    "${AZURITE_PORTS[2]}" "$BLUEPRINT_PORT" "$CONTROL_PLANE_PORT" \
    "$FUNCTIONS_PORT" "$WORLD_MINUTES_PER_SECOND"
}

source_is_clean() {
  [[ -z "$(git status --porcelain --untracked-files=all)" ]]
}

check_source() {
  if source_is_clean; then
    printf 'clean-source guard: PASS\n'
    return 0
  fi
  printf '%s\n' \
    'clean-source guard: working tree is dirty; use --dirty-development for a non-attributed proof' \
    >&2
  return 3
}

case "${1:-}" in
  --print-config)
    print_config
    exit 0
    ;;
  --check-source)
    check_source
    exit $?
    ;;
  --dirty-development)
    DIRTY_DEVELOPMENT=1
    ;;
  --replay-only)
    MODE="replay-only"
    DIRTY_DEVELOPMENT=1
    ;;
  "")
    ;;
  *)
    printf 'unknown option: %s\n' "$1" >&2
    exit 2
    ;;
esac

if [[ "$DIRTY_DEVELOPMENT" -eq 0 ]]; then
  check_source
fi

for required in azurite curl func git lsof node uv; do
  command -v "$required" >/dev/null || {
    printf 'missing required command: %s\n' "$required" >&2
    exit 2
  }
done

export ACTOR_PROOF_ROOT="$RUNTIME_DIR"
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

CONTROL_PLANE_PID=""
BLUEPRINT_PID=""
REPLAY_API_PID=""
CLEANED=0
ALL_PORTS=(
  "${AZURITE_PORTS[@]}"
  "$FUNCTIONS_PORT"
  "$API_PORT"
  "$CONTROL_PLANE_PORT"
  "$BLUEPRINT_PORT"
)

kill_started() {
  [[ "$CLEANED" -eq 1 ]] && return 0
  CLEANED=1
  kill_tree "$REPLAY_API_PID" "replay-fastapi"
  kill_tree "$CONTROL_PLANE_PID" "control-plane"
  kill_tree "$BLUEPRINT_PID" "blueprint"
  teardown_stack
}
trap kill_started EXIT INT TERM

wait_http() {
  local url="$1" label="$2" pid="$3" log_file="$4" attempts="${5:-60}"
  local _
  for _ in $(seq 1 "$attempts"); do
    if ! kill -0 "$pid" 2>/dev/null; then
      printf '%s exited early\n' "$label" >&2
      tail -n 50 "$log_file" >&2 || true
      return 1
    fi
    if curl -fsS --max-time 4 "$url" >/dev/null 2>&1; then
      printf '==> %s ready (pid %s)\n' "$label" "$pid"
      return 0
    fi
    sleep 1
  done
  printf '%s did not become ready: %s\n' "$label" "$url" >&2
  tail -n 50 "$log_file" >&2 || true
  return 1
}

start_control_plane() {
  local log_file="$PROOF_DIR/logs/control-plane.log"
  ( exec env \
      VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
      VITE_BLUEPRINT_URL="http://127.0.0.1:$BLUEPRINT_PORT" \
      "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 \
      --port "$CONTROL_PLANE_PORT" --strictPort ) \
    >"$log_file" 2>&1 &
  CONTROL_PLANE_PID=$!
  wait_http "http://127.0.0.1:$CONTROL_PLANE_PORT/world" \
    "Control Plane" "$CONTROL_PLANE_PID" "$log_file"
}

start_blueprint() {
  local log_file="$PROOF_DIR/logs/blueprint.log"
  ( cd "$ROOT/web/blueprint" \
      && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
        "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 \
        --port "$BLUEPRINT_PORT" --strictPort ) \
    >"$log_file" 2>&1 &
  BLUEPRINT_PID=$!
  wait_http "http://127.0.0.1:$BLUEPRINT_PORT/?view=constellation" \
    "Blueprint" "$BLUEPRINT_PID" "$log_file"
}

start_replay_api() {
  local log_file="$PROOF_DIR/logs/replay-api.log"
  ( exec env \
      -u ZAVA_WORLD \
      -u FUNCTIONS_HOST \
      ZAVA_VERTICAL=fashion \
      ZAVA_BLUEPRINT_REPLAY_ONLY=1 \
      PORTAL_DATA_DIR="$RUNTIME_DIR/replay-portal" \
      ENTITY_PLANE_ENABLED=0 \
      SIMULATOR_RAMP_ENABLED=0 \
      BLUEPRINT_RECORDINGS_DIR="$PROOF_DIR/recordings" \
      uv run --frozen --no-sync uvicorn api.server.main:app \
      --host 127.0.0.1 --port "$API_PORT" ) \
    >"$log_file" 2>&1 &
  REPLAY_API_PID=$!
  wait_http "http://127.0.0.1:$API_PORT/healthz" \
    "Replay FastAPI" "$REPLAY_API_PID" "$log_file"
}

write_teardown_result() {
  local busy=0 port
  for port in "${ALL_PORTS[@]}"; do
    if port_listening "$port"; then
      printf 'proof port %s is still listening after teardown\n' "$port" >&2
      busy=1
    fi
  done
  uv run --frozen --no-sync python - "$PROOF_DIR/replay-summary.json" "$busy" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
busy = int(sys.argv[2])
if path.is_file():
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["cleanTeardown"] = "PASS" if busy == 0 else "FAIL"
    if busy:
        payload["result"] = "FAIL"
        payload["substrate_result"] = "FAIL"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
PY
  return "$busy"
}

if [[ "$MODE" == "full" ]]; then
  rm -rf "$PROOF_DIR"
  mkdir -p "$PROOF_DIR/logs" "$PROOF_DIR/recordings"
  cp "$ROOT"/verticals/fashion/recordings/*.jsonl "$PROOF_DIR/recordings/"
  export PORTAL_DATA_DIR="$RUNTIME_DIR/portal"
  export ENTITY_GRAPH_PATH="$RUNTIME_DIR/entity_graph.kuzu"
  export MEMORY_FALLBACK_DIR="$RUNTIME_DIR/memory"
  export BLUEPRINT_RECORDINGS_DIR="$PROOF_DIR/recordings"
  export ZAVA_VERTICAL="fashion"
  export SIMULATOR_RAMP_ENABLED="0"
  export DREAM_PASS_DEMO_CADENCE_SECONDS="0"
  export ENTITY_PLANE_ENABLED="1"
  export AGT_ENFORCE="1"
  export MAX_OBSERVATORY_EVENTS_PER_SEC="10000"
  export DURABLE_EVENT_SECRET="fashion-proof-local-isolated"
  export FASTAPI_WEBHOOK_URL="http://127.0.0.1:$API_PORT/internal/durable-event"
  export CORS_ALLOWED_ORIGINS="http://127.0.0.1:$CONTROL_PLANE_PORT,http://127.0.0.1:$BLUEPRINT_PORT,http://127.0.0.1:$API_PORT"
  export AzureWebJobsStorage="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:${AZURITE_PORTS[0]}/devstoreaccount1;QueueEndpoint=http://127.0.0.1:${AZURITE_PORTS[1]}/devstoreaccount1;TableEndpoint=http://127.0.0.1:${AZURITE_PORTS[2]}/devstoreaccount1;"

  preflight_ports "${ALL_PORTS[@]}"
  start_azurite
  start_functions_host
  for orchestrator in \
    InventoryRebalancingOrchestrator \
    DemandSpikeResponseOrchestrator \
    PromotionReadinessOrchestrator \
    MarkdownGovernanceOrchestrator \
    SupplierDelayRecoveryOrchestrator \
    FulfilmentExceptionResolutionOrchestrator \
    MarketplaceSellerExceptionOrchestrator \
    ReturnsDispositionOrchestrator; do
    grep -q "$orchestrator" "$FUNC_LOG" || {
      printf 'Functions host did not index %s\n' "$orchestrator" >&2
      exit 4
    }
  done
  start_fastapi
  start_control_plane
  start_blueprint

  set +e
  CONTROL_PLANE_BASE="http://127.0.0.1:$CONTROL_PLANE_PORT" \
  BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
  WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
  FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT" \
  PROOF_OUT_DIR="$PROOF_DIR" \
    node "$DRIVER"
  rc=$?
  set -e
  cp "$AZ_LOG" "$FUNC_LOG" "$API_LOG" "$PROOF_DIR/logs/" 2>/dev/null || true
  [[ "$rc" -eq 0 ]] || exit "$rc"

  kill_tree "$API_PID" "live-fastapi"
  API_PID=""
  kill_tree "$FUNC_PID" "functions-host"
  FUNC_PID=""
  kill_tree "$AZ_PID" "azurite"
  AZ_PID=""
  sleep 1
else
  test -f "$PROOF_DIR/live-summary.json" || {
    printf 'replay evidence missing: %s/live-summary.json\n' "$PROOF_DIR" >&2
    exit 2
  }
  mkdir -p "$PROOF_DIR/logs" "$PROOF_DIR/recordings"
fi

start_replay_api
if [[ -z "$CONTROL_PLANE_PID" ]]; then
  start_control_plane
fi
if [[ -z "$BLUEPRINT_PID" ]]; then
  start_blueprint
fi

set +e
CONTROL_PLANE_BASE="http://127.0.0.1:$CONTROL_PLANE_PORT" \
BLUEPRINT_BASE="http://127.0.0.1:$BLUEPRINT_PORT" \
WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
FUNCTIONS_HOST="http://127.0.0.1:$FUNCTIONS_PORT" \
PROOF_OUT_DIR="$PROOF_DIR" \
  node "$DRIVER" --replay
rc=$?
set -e

kill_started
trap - EXIT INT TERM
sleep 1
if ! write_teardown_result; then
  rc=9
fi

writer_args=(--proof-dir "$PROOF_DIR")
if [[ "$DIRTY_DEVELOPMENT" -eq 1 ]]; then
  writer_args+=(--dirty-development)
fi
set +e
uv run --frozen --no-sync python tools/fashion_proof_manifest.py "${writer_args[@]}"
manifest_rc=$?
set -e
if [[ "$manifest_rc" -ne 0 && "$rc" -eq 0 ]]; then
  rc="$manifest_rc"
fi

if [[ "$rc" -eq 0 ]]; then
  printf 'FASHION ZAVA E2E PROOF PASSED (seller review remains PENDING)\n'
else
  printf 'FASHION ZAVA E2E PROOF FAILED (exit %s)\n' "$rc" >&2
fi
exit "$rc"
