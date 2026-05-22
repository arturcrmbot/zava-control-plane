#!/usr/bin/env bash
# Record a replay tape with the substrate fully alive (DEMO_LOUD on).
#
# Usage:
#   DURATION=5m OUT=tapes/smoke.tar.gz scripts/record_tape.sh
#   DURATION=30m OUT=tapes/medium.tar.gz scripts/record_tape.sh
#   DURATION=2h  OUT=tapes/landing.tar.gz scripts/record_tape.sh
#
# DURATION accepts: NNs / NNm / NNh.
# Sends SIGTERM after the requested duration so the recorder finalises
# cleanly. A manual Ctrl-C also works but is bounded by --min-seconds.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DURATION="${DURATION:-5m}"
OUT="${OUT:?OUT=path/to/tape.tar.gz required}"
STARTUP_GRACE_SECONDS="${STARTUP_GRACE_SECONDS:-2}"

case "$DURATION" in
  *s) SECS="${DURATION%s}" ;;
  *m) SECS=$(( ${DURATION%m} * 60 )) ;;
  *h) SECS=$(( ${DURATION%h} * 3600 )) ;;
  *) echo "DURATION must end with s/m/h, got: $DURATION" >&2; exit 2 ;;
esac

cd "$REPO_ROOT"

export DEMO_LOUD=1
export DREAM_PASS_DEMO_CADENCE_SECONDS=180
export DREAM_PASS_TRIGGER_BACKLOG=5
export MEMORY_DOMAINS=hiring
export ZAVA_APP_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
export PORTAL_DATA_DIR="${PORTAL_DATA_DIR:-${REPO_ROOT}/tapes/.portal-data}"

mkdir -p "$(dirname "$OUT")" "$PORTAL_DATA_DIR"
echo "[record_tape] DURATION=${DURATION} (${SECS}s) OUT=${OUT} APP_SHA=${ZAVA_APP_SHA}"

uv run python scripts/_record_entrypoint.py --out "$OUT" --min-seconds "$SECS" &
PID=$!
STOP_REQUESTED=0

request_stop() {
  STOP_REQUESTED=1
}
trap request_stop INT TERM

sleep "$(( SECS + STARTUP_GRACE_SECONDS ))" || true

process_running() {
  local state
  state="$(ps -o stat= -p "$PID" 2>/dev/null || true)"
  [[ -n "$state" && "$state" != Z* ]]
}

for _ in 1 2 3; do
  kill -TERM "$PID" 2>/dev/null || true
  sleep 1
  if ! process_running; then
    break
  fi
done

wait "$PID"
STATUS=$?

if [[ "$STOP_REQUESTED" == "1" ]]; then
  echo "[record_tape] interrupted → $OUT"
else
  echo "[record_tape] done → $OUT"
fi
exit "$STATUS"
