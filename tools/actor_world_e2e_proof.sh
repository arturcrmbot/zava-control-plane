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
# The shared backend boot/teardown lives in tools/lib/actor_world_proof_stack.sh
# (also used by the browser viewer proof). Teardown kills only the exact PIDs
# this script started, plus their discovered descendants; never pkill/killall.
#
# Usage:  bash tools/actor_world_e2e_proof.sh
set -uo pipefail

# shellcheck source=tools/lib/actor_world_proof_stack.sh
source "$(cd "$(dirname "$0")" && pwd)/lib/actor_world_proof_stack.sh"
cd "$ROOT"

ALL_PORTS=("${AZ_PORTS[@]}" "$FUNC_PORT" "$API_PORT")
CLEANED=""

cleanup() {
  [ -n "$CLEANED" ] && return 0
  CLEANED=1
  echo
  log "tearing down"
  teardown_stack
  sleep 1
  report_ports_released "${ALL_PORTS[@]}"
}
trap cleanup EXIT INT TERM

# -- boot the shared real stack ----------------------------------------------
preflight_ports "${ALL_PORTS[@]}"
start_azurite
start_functions_host
start_fastapi

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
