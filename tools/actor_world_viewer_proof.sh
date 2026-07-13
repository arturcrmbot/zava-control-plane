#!/usr/bin/env bash
# Browser proof of the Observable World Viewer (plan
# 2026-07-13-observable-world-viewer, Task 4). Boots the SAME fresh, isolated,
# unmocked backend as the CLI proof — via tools/lib/actor_world_proof_stack.sh —
# plus the Control Plane Vite dev server on :5273, then runs the Playwright
# assertion driver against the real /world route:
#
#   Azurite (:10000-10002) → Functions host (:7071) → FastAPI (:3101, support)
#   → Control Plane Vite (:5273, proxies /api → FastAPI)
#
# tools/actor_world_viewer_proof.mjs asserts the viewer renders the real actor
# world (baseline workers/tickets → surge → queue pressure → real Durable
# intervention → reallocated workers in the support group → later resolved
# ticket), cross-checking the DOM against the JSON journal and the Durable
# runtime on :7071. Evidence (screenshots, video, summary) lands under
# tmp/actor-world-viewer-proof/.
#
# Teardown kills only the exact PIDs this script started (Vite here, backend in
# the shared helper), plus their discovered descendants — never pkill/killall.
#
# Usage:  bash tools/actor_world_viewer_proof.sh
set -uo pipefail

# shellcheck source=tools/lib/actor_world_proof_stack.sh
source "$(cd "$(dirname "$0")" && pwd)/lib/actor_world_proof_stack.sh"
cd "$ROOT"

UI_PORT=5273
VITE_LOG="$COMPOSE_DIR/actor-viewer-vite.log"
VITE_PID=""
ALL_PORTS=("${AZ_PORTS[@]}" "$FUNC_PORT" "$API_PORT" "$UI_PORT")
OUT_DIR="$ROOT/tmp/actor-world-viewer-proof"
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

# -- boot the shared real backend + a fresh evidence dir ---------------------
preflight_ports "${ALL_PORTS[@]}"
rm -rf "$OUT_DIR"
start_azurite
start_functions_host
start_fastapi

# -- Control Plane Vite (:5273, proxying /api → FastAPI) ---------------------
log "starting Control Plane Vite (:$UI_PORT)"
( cd "$ROOT" \
    && exec env VITE_API_BASE_URL="http://127.0.0.1:$API_PORT" \
         "$ROOT/node_modules/.bin/vite" --host 127.0.0.1 --port "$UI_PORT" --strictPort ) \
  >"$VITE_LOG" 2>&1 &
VITE_PID=$!
echo "$VITE_PID" >"$COMPOSE_DIR/actor-viewer-vite.pid"

vite_ready=""
for _ in $(seq 1 60); do
  if ! kill -0 "$VITE_PID" 2>/dev/null; then
    err "Vite exited early; log tail:"; tail -n 30 "$VITE_LOG" >&2; exit 6
  fi
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$UI_PORT/" 2>/dev/null)"
  if [ "$code" = "200" ]; then
    # Serving the app AND proxying /api through to the live actor world.
    if curl -s --max-time 10 "http://127.0.0.1:$UI_PORT/api/world/state" 2>/dev/null \
         | grep -q '"scenario": *"support"'; then
      vite_ready=1; break
    fi
  fi
  sleep 1
done
[ -n "$vite_ready" ] || { err "Vite/world route never became ready"; tail -n 30 "$VITE_LOG" >&2; exit 6; }
log "Vite ready; /world served and /api proxied (pid $VITE_PID)"

# -- Drive the browser proof -------------------------------------------------
log "running Playwright assertion driver"
WORLD_UI_BASE="http://127.0.0.1:$UI_PORT" \
WORLD_API_BASE="http://127.0.0.1:$API_PORT" \
FUNCTIONS_HOST="http://127.0.0.1:$FUNC_PORT" \
PROOF_OUT_DIR="$OUT_DIR" \
  node tools/actor_world_viewer_proof.mjs
rc=$?

echo
if [ "$rc" -eq 0 ]; then
  log "VIEWER PROOF PASSED"
  log "evidence: $OUT_DIR"
else
  err "VIEWER PROOF FAILED (driver exit $rc)"
  err "Vite log tail:"; tail -n 20 "$VITE_LOG" >&2
  err "FastAPI log tail:"; tail -n 20 "$API_LOG" >&2
  err "Functions log tail:"; tail -n 20 "$FUNC_LOG" >&2
fi
exit "$rc"
