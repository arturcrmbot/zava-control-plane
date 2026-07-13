#!/usr/bin/env bash
# Real end-to-end proof of the actor → Durable → worker command loop (Plan 2,
# Task 6). Boots a fresh, isolated stack — no mocks — and runs the assertion
# driver against it:
#
#   Azurite (:10000-10002)  →  Functions host (:7071, SurgeStaffingOrchestrator)
#   FastAPI (:3101, ZAVA_WORLD=support WORLD_SEED=42 WORLD_MINUTES_PER_SECOND=10)
#
# The live actor world trips a real sensor, a REAL Durable orchestration decides
# a typed reallocate_workers command, and the runtime moves real reserve
# workers. tools/actor_world_e2e_proof.py asserts the whole chain and writes
# evidence under tmp/actor-world-e2e-proof/.
#
# Teardown kills only the exact PIDs this script started, plus their discovered
# descendants (func spawns a host + Python worker; uv spawns uvicorn). setsid is
# unavailable on macOS, so we snapshot each process tree with `pgrep -P` before
# killing — never pkill/killall.
#
# Usage:  bash tools/actor_world_e2e_proof.sh
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE_DIR="$ROOT/.compose"
AZ_DATA="$COMPOSE_DIR/actor-proof-azurite"
AZ_LOG="$COMPOSE_DIR/actor-proof-azurite.log"
FUNC_LOG="$COMPOSE_DIR/actor-proof-func.log"
API_LOG="$COMPOSE_DIR/actor-proof-api.log"

AZ_PORTS=(10000 10001 10002)
FUNC_PORT=7071
API_PORT=3101
ALL_PORTS=("${AZ_PORTS[@]}" "$FUNC_PORT" "$API_PORT")

AZ_PID=""
FUNC_PID=""
API_PID=""
CLEANED=""

log() { printf '==> %s\n' "$*"; }
err() { printf 'ERROR: %s\n' "$*" >&2; }

port_listening() { lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1; }

# Print a PID and all of its descendants, children before parents, so callers
# can terminate leaves first. Snapshot this BEFORE killing anything: once a
# parent dies its children reparent to launchd and pgrep -P can't find them.
collect_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null); do
    collect_tree "$child"
  done
  printf '%s\n' "$pid"
}

kill_tree() {
  local root="$1" label="$2"
  [ -n "$root" ] || return 0
  local pids
  pids="$(collect_tree "$root")"
  [ -n "$pids" ] || return 0
  log "stopping $label (pids: $(echo "$pids" | tr '\n' ' '))"
  local p
  for p in $pids; do kill -TERM "$p" 2>/dev/null; done
  local waited
  for waited in $(seq 1 20); do
    local alive=""
    for p in $pids; do kill -0 "$p" 2>/dev/null && alive="$alive $p"; done
    [ -z "$alive" ] && return 0
    sleep 0.5
  done
  for p in $pids; do kill -0 "$p" 2>/dev/null && kill -KILL "$p" 2>/dev/null; done
}

cleanup() {
  [ -n "$CLEANED" ] && return 0
  CLEANED=1
  echo
  log "tearing down"
  kill_tree "$API_PID" "fastapi"
  kill_tree "$FUNC_PID" "functions-host"
  kill_tree "$AZ_PID" "azurite"
  # Verify the ports we own were released.
  sleep 1
  local still=""
  local port
  for port in "${ALL_PORTS[@]}"; do
    port_listening "$port" && still="$still $port"
  done
  if [ -n "$still" ]; then
    err "ports still LISTENING after teardown:$still"
  else
    log "all ports released (${ALL_PORTS[*]})"
  fi
}
trap cleanup EXIT INT TERM

# -- preflight: every port must be free --------------------------------------
busy=""
for port in "${ALL_PORTS[@]}"; do
  port_listening "$port" && busy="$busy $port"
done
if [ -n "$busy" ]; then
  err "required ports already in use:$busy"
  err "free them (another Azurite/func/uvicorn?) and retry."
  exit 2
fi

mkdir -p "$COMPOSE_DIR"
rm -rf "$AZ_DATA"
mkdir -p "$AZ_DATA"

# -- Azurite -----------------------------------------------------------------
log "starting Azurite (${AZ_PORTS[*]})"
( exec azurite --silent --location "$AZ_DATA" \
    --blobHost 127.0.0.1 --queueHost 127.0.0.1 --tableHost 127.0.0.1 ) \
  >"$AZ_LOG" 2>&1 &
AZ_PID=$!
echo "$AZ_PID" >"$COMPOSE_DIR/actor-proof-azurite.pid"

az_ready=""
for _ in $(seq 1 30); do
  if ! kill -0 "$AZ_PID" 2>/dev/null; then
    err "Azurite exited early; log tail:"; tail -n 20 "$AZ_LOG" >&2; exit 3
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:10000/devstoreaccount1 2>/dev/null)"
  if [ "$code" = "400" ]; then az_ready=1; break; fi
  sleep 1
done
[ -n "$az_ready" ] || { err "Azurite did not become ready"; tail -n 20 "$AZ_LOG" >&2; exit 3; }
log "Azurite ready (pid $AZ_PID)"

# -- Functions host ----------------------------------------------------------
# Use the repo venv for the Python worker; func itself is the system binary.
# ENTITY_PLANE_ENABLED=0 keeps this focused on the world responder.
log "starting Functions host (:$FUNC_PORT)"
( cd "$ROOT" \
    && source .venv/bin/activate \
    && exec env ENTITY_PLANE_ENABLED=0 PYTHONPATH="$ROOT" \
         func start --port "$FUNC_PORT" ) \
  >"$FUNC_LOG" 2>&1 &
FUNC_PID=$!
echo "$FUNC_PID" >"$COMPOSE_DIR/actor-proof-func.pid"

func_ready=""
for _ in $(seq 1 60); do
  if ! kill -0 "$FUNC_PID" 2>/dev/null; then
    err "Functions host exited early; log tail:"; tail -n 30 "$FUNC_LOG" >&2; exit 4
  fi
  # Ready only when the host has indexed our orchestrator AND serves HTTP.
  if grep -q "SurgeStaffingOrchestrator" "$FUNC_LOG" 2>/dev/null \
     && curl -s -o /dev/null http://127.0.0.1:"$FUNC_PORT"/admin/host/status 2>/dev/null; then
    func_ready=1; break
  fi
  sleep 2
done
[ -n "$func_ready" ] || { err "Functions host never indexed SurgeStaffingOrchestrator"; tail -n 40 "$FUNC_LOG" >&2; exit 4; }
log "Functions host ready; SurgeStaffingOrchestrator indexed (pid $FUNC_PID)"

# -- FastAPI (live actor world) ----------------------------------------------
log "starting FastAPI (:$API_PORT, ZAVA_WORLD=support seed=42 mps=10)"
( cd "$ROOT" \
    && exec env ZAVA_WORLD=support WORLD_SEED=42 WORLD_MINUTES_PER_SECOND=10 \
         FUNCTIONS_HOST="http://127.0.0.1:$FUNC_PORT" \
         uv run --frozen --no-sync uvicorn api.server.main:app \
           --host 127.0.0.1 --port "$API_PORT" ) \
  >"$API_LOG" 2>&1 &
API_PID=$!
echo "$API_PID" >"$COMPOSE_DIR/actor-proof-api.pid"

api_ready=""
for _ in $(seq 1 45); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    err "FastAPI exited early; log tail:"; tail -n 30 "$API_LOG" >&2; exit 5
  fi
  health="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:"$API_PORT"/healthz 2>/dev/null)"
  if [ "$health" = "200" ]; then
    # Health is up; require the actor world to actually be enabled + support.
    if curl -s http://127.0.0.1:"$API_PORT"/api/world/state 2>/dev/null \
         | grep -q '"scenario": *"support"'; then
      api_ready=1; break
    fi
  fi
  sleep 1
done
[ -n "$api_ready" ] || { err "FastAPI/actor world never became ready"; tail -n 30 "$API_LOG" >&2; exit 5; }
log "FastAPI ready; actor world enabled (pid $API_PID)"

# -- Drive the proof ---------------------------------------------------------
log "running assertion driver"
WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
FUNCTIONS_HOST="http://127.0.0.1:$FUNC_PORT" \
  uv run --frozen --no-sync python tools/actor_world_e2e_proof.py
rc=$?

echo
if [ "$rc" -eq 0 ]; then
  log "PROOF PASSED"
else
  err "PROOF FAILED (driver exit $rc)"
  err "FastAPI log tail:"; tail -n 25 "$API_LOG" >&2
  err "Functions log tail:"; tail -n 25 "$FUNC_LOG" >&2
fi
exit "$rc"
