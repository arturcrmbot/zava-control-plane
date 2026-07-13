#!/usr/bin/env bash
# Real end-to-end browser proof of the telco Network Incident world
# (feat(telco)). Boots the SAME fresh, isolated, unmocked backend as the support
# viewer proof — via tools/lib/actor_world_proof_stack.sh, parametrised for the
# telco scenario — plus a Control Plane Vite dev server, then runs the Playwright
# assertion driver against the real /world route:
#
#   Azurite (:10000-10002) → Functions host (:7071, NetworkIncidentOrchestrator)
#   → FastAPI (:3101, ZAVA_WORLD=telco) → Control Plane Vite (:5280, /api proxy)
#
# tools/telco_world_e2e_proof.mjs asserts the viewer renders the REAL actor
# world (baseline cell-site + session actor IDs → injected site failure →
# degraded sessions → real Durable NetworkIncidentOrchestrator decision →
# rerouted sessions on healthy neighbours → recovered site), cross-checking the
# DOM against the JSON journal and the Durable runtime on :7071. Evidence
# (screenshots, video, summary) lands under tmp/telco-world-e2e-proof/.
#
# Teardown kills only the exact PIDs this script started (Vite here, backend in
# the shared helper) plus their discovered descendants — never pkill/killall.
#
# Usage:  bash tools/telco_world_e2e_proof.sh
set -uo pipefail

# Drive the shared stack as the telco scenario. Defaults in the library keep the
# support proofs booting an identical support stack; these overrides are the ONLY
# telco-specific knobs — no copied boot logic.
export PROOF_WORLD="telco"
export PROOF_ORCHESTRATOR_GREP="NetworkIncidentOrchestrator"
export PROOF_SEED="${PROOF_SEED:-42}"
export PROOF_MPS="${PROOF_MPS:-3}"

# shellcheck source=tools/lib/actor_world_proof_stack.sh
source "$(cd "$(dirname "$0")" && pwd)/lib/actor_world_proof_stack.sh"
cd "$ROOT"

UI_PORT="${TELCO_UI_PORT:-5280}"
VITE_LOG="$COMPOSE_DIR/telco-viewer-vite.log"
VITE_PID=""
ALL_PORTS=("${AZ_PORTS[@]}" "$FUNC_PORT" "$API_PORT" "$UI_PORT")
OUT_DIR="$ROOT/tmp/telco-world-e2e-proof"
CLEANED=""

cleanup() {
  [ -n "$CLEANED" ] && return 0
  CLEANED=1
  echo
  log "tearing down"
  kill_tree "$VITE_PID" "vite"
  teardown_stack
  sleep 1
  report_ports_released "${ALL_PORTS[@]}"
}
trap cleanup EXIT INT TERM

# -- boot the shared real backend (telco) + a fresh evidence dir -------------
preflight_ports "${ALL_PORTS[@]}"
rm -rf "$OUT_DIR"
start_azurite
start_functions_host
start_fastapi

# -- Control Plane Vite (proxying /api → FastAPI) ----------------------------
log "starting Control Plane Vite (:$UI_PORT)"
( cd "$ROOT" \
    && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
         "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$UI_PORT" --strictPort ) \
  >"$VITE_LOG" 2>&1 &
VITE_PID=$!
echo "$VITE_PID" >"$COMPOSE_DIR/telco-viewer-vite.pid"

vite_ready=""
for _ in $(seq 1 60); do
  if ! kill -0 "$VITE_PID" 2>/dev/null; then
    err "Vite exited early; log tail:"; tail -n 30 "$VITE_LOG" >&2; exit 6
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$UI_PORT/" 2>/dev/null)"
  if [ "$code" = "200" ]; then
    # Serving the app AND proxying /api through to the live telco actor world.
    if curl -s --max-time 10 "http://127.0.0.1:$UI_PORT/api/world/state" 2>/dev/null \
         | grep -q '"scenario": *"telco"'; then
      vite_ready=1; break
    fi
  fi
  sleep 1
done
[ -n "$vite_ready" ] || { err "Vite/telco world route never became ready"; tail -n 30 "$VITE_LOG" >&2; exit 6; }
log "Vite ready; /world served and /api proxied to the telco world (pid $VITE_PID)"

# -- Drive the browser proof -------------------------------------------------
log "running Playwright assertion driver"
WORLD_UI_BASE="http://127.0.0.1:$UI_PORT" \
WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
FUNCTIONS_HOST="http://127.0.0.1:$FUNC_PORT" \
PROOF_OUT_DIR="$OUT_DIR" \
  node tools/telco_world_e2e_proof.mjs
rc=$?

echo
if [ "$rc" -eq 0 ]; then
  log "TELCO WORLD E2E PROOF PASSED"
  log "evidence: $OUT_DIR"
else
  err "TELCO WORLD E2E PROOF FAILED (driver exit $rc)"
  err "Vite log tail:"; tail -n 20 "$VITE_LOG" >&2
  err "FastAPI log tail:"; tail -n 20 "$API_LOG" >&2
  err "Functions log tail:"; tail -n 20 "$FUNC_LOG" >&2
fi
exit "$rc"
