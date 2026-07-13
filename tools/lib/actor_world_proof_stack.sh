#!/usr/bin/env bash
# Shared real-stack boot/teardown for the actor-world proofs.
#
# Both the CLI proof (tools/actor_world_e2e_proof.sh) and the browser/viewer
# proof (tools/actor_world_viewer_proof.sh) need the SAME fresh, isolated,
# unmocked backend:
#
#   Azurite (:10000-10002)  →  Functions host (:7071, SurgeStaffingOrchestrator)
#   FastAPI (:3101, ZAVA_WORLD=support WORLD_SEED=42 WORLD_MINUTES_PER_SECOND=10)
#
# This library owns exactly that shared boot and its exact-PID teardown — no
# more. It is NOT a generic process framework: each proof still owns its own
# preflight, trap, extra processes (e.g. the viewer's Vite server) and driver.
#
# Contract for callers:
#   * source this file, then define a cleanup() that calls teardown_stack and
#     install it as an EXIT/INT/TERM trap BEFORE starting anything, so a failed
#     start_* still tears down.
#   * call preflight_ports with the full port set the proof will use.
#   * call start_azurite / start_functions_host / start_fastapi in order.
#   * a fatal start failure calls `exit` (firing the caller's trap); success
#     leaves AZ_PID / FUNC_PID / API_PID set.
#
# setsid is unavailable on macOS, so teardown snapshots each process tree with
# `pgrep -P` before killing — never pkill/killall.

# Repo root, derived from this library's own location (tools/lib/..).
_STACK_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$_STACK_LIB_DIR/../.." && pwd)"

COMPOSE_DIR="$ROOT/.compose"
AZ_DATA="$COMPOSE_DIR/actor-proof-azurite"
AZ_LOG="$COMPOSE_DIR/actor-proof-azurite.log"
FUNC_LOG="$COMPOSE_DIR/actor-proof-func.log"
API_LOG="$COMPOSE_DIR/actor-proof-api.log"

AZ_PORTS=(10000 10001 10002)
FUNC_PORT=7071
API_PORT=3101

# Scenario knobs. Defaults reproduce the original support proof exactly, so the
# support proofs keep booting an identical stack. The telco proof overrides
# these via the environment (ZAVA_WORLD=telco, its own orchestrator name) so a
# single shared boot library serves both scenarios — no copied stack.
PROOF_WORLD="${PROOF_WORLD:-support}"
PROOF_SEED="${PROOF_SEED:-42}"
PROOF_MPS="${PROOF_MPS:-10}"
PROOF_ORCHESTRATOR_GREP="${PROOF_ORCHESTRATOR_GREP:-SurgeStaffingOrchestrator}"

AZ_PID=""
FUNC_PID=""
API_PID=""

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

# preflight_ports PORT...  — abort (exit 2) if any given port is already bound.
preflight_ports() {
  local busy="" port
  for port in "$@"; do
    port_listening "$port" && busy="$busy $port"
  done
  if [ -n "$busy" ]; then
    err "required ports already in use:$busy"
    err "free them (another Azurite/func/uvicorn/vite?) and retry."
    exit 2
  fi
}

# teardown_stack — kill only the exact backend PIDs this library started, plus
# their discovered descendants (leaves first). Idempotent per PID.
teardown_stack() {
  kill_tree "$API_PID" "fastapi"
  kill_tree "$FUNC_PID" "functions-host"
  kill_tree "$AZ_PID" "azurite"
}

# report_ports_released PORT...  — after teardown, confirm the proof's ports are
# free again; warn (do not fail) if any remain bound.
report_ports_released() {
  local still="" port
  for port in "$@"; do
    port_listening "$port" && still="$still $port"
  done
  if [ -n "$still" ]; then
    err "ports still LISTENING after teardown:$still"
  else
    log "all ports released ($*)"
  fi
}

# -- Azurite -----------------------------------------------------------------
start_azurite() {
  mkdir -p "$COMPOSE_DIR"
  rm -rf "$AZ_DATA"
  mkdir -p "$AZ_DATA"

  log "starting Azurite (${AZ_PORTS[*]})"
  ( exec azurite --silent --location "$AZ_DATA" \
      --blobHost 127.0.0.1 --queueHost 127.0.0.1 --tableHost 127.0.0.1 ) \
    >"$AZ_LOG" 2>&1 &
  AZ_PID=$!
  echo "$AZ_PID" >"$COMPOSE_DIR/actor-proof-azurite.pid"

  local ready="" _
  for _ in $(seq 1 30); do
    if ! kill -0 "$AZ_PID" 2>/dev/null; then
      err "Azurite exited early; log tail:"; tail -n 20 "$AZ_LOG" >&2; exit 3
    fi
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:10000/devstoreaccount1 2>/dev/null)"
    if [ "$code" = "400" ]; then ready=1; break; fi
    sleep 1
  done
  [ -n "$ready" ] || { err "Azurite did not become ready"; tail -n 20 "$AZ_LOG" >&2; exit 3; }
  log "Azurite ready (pid $AZ_PID)"
}

# -- Functions host ----------------------------------------------------------
# Use the repo venv for the Python worker; func itself is the system binary.
# ENTITY_PLANE_ENABLED=0 keeps this focused on the world responder.
start_functions_host() {
  log "starting Functions host (:$FUNC_PORT)"
  ( cd "$ROOT" \
      && source .venv/bin/activate \
      && exec env ENTITY_PLANE_ENABLED=0 PYTHONPATH="$ROOT" \
           func start --port "$FUNC_PORT" ) \
    >"$FUNC_LOG" 2>&1 &
  FUNC_PID=$!
  echo "$FUNC_PID" >"$COMPOSE_DIR/actor-proof-func.pid"

  local ready="" _
  for _ in $(seq 1 60); do
    if ! kill -0 "$FUNC_PID" 2>/dev/null; then
      err "Functions host exited early; log tail:"; tail -n 30 "$FUNC_LOG" >&2; exit 4
    fi
    # Ready only when the host has indexed our orchestrator AND serves HTTP.
    if grep -q "$PROOF_ORCHESTRATOR_GREP" "$FUNC_LOG" 2>/dev/null \
       && curl -s -o /dev/null http://127.0.0.1:"$FUNC_PORT"/admin/host/status 2>/dev/null; then
      ready=1; break
    fi
    sleep 2
  done
  [ -n "$ready" ] || { err "Functions host never indexed $PROOF_ORCHESTRATOR_GREP"; tail -n 40 "$FUNC_LOG" >&2; exit 4; }
  log "Functions host ready; $PROOF_ORCHESTRATOR_GREP indexed (pid $FUNC_PID)"
}

# -- FastAPI (live actor world) ----------------------------------------------
start_fastapi() {
  log "starting FastAPI (:$API_PORT, ZAVA_WORLD=$PROOF_WORLD seed=$PROOF_SEED mps=$PROOF_MPS)"
  ( cd "$ROOT" \
      && exec env ZAVA_WORLD="$PROOF_WORLD" WORLD_SEED="$PROOF_SEED" WORLD_MINUTES_PER_SECOND="$PROOF_MPS" \
           FUNCTIONS_HOST="http://127.0.0.1:$FUNC_PORT" \
           uv run --frozen --no-sync uvicorn api.server.main:app \
             --host 127.0.0.1 --port "$API_PORT" ) \
    >"$API_LOG" 2>&1 &
  API_PID=$!
  echo "$API_PID" >"$COMPOSE_DIR/actor-proof-api.pid"

  local ready="" _
  for _ in $(seq 1 45); do
    if ! kill -0 "$API_PID" 2>/dev/null; then
      err "FastAPI exited early; log tail:"; tail -n 30 "$API_LOG" >&2; exit 5
    fi
    local health
    health="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:"$API_PORT"/healthz 2>/dev/null)"
    if [ "$health" = "200" ]; then
      # Health is up; require the actor world to actually be enabled + scenario.
      if curl -s http://127.0.0.1:"$API_PORT"/api/world/state 2>/dev/null \
           | grep -q "\"scenario\": *\"$PROOF_WORLD\""; then
        ready=1; break
      fi
    fi
    sleep 1
  done
  [ -n "$ready" ] || { err "FastAPI/actor world never became ready"; tail -n 30 "$API_LOG" >&2; exit 5; }
  log "FastAPI ready; actor world enabled (pid $API_PID)"
}
