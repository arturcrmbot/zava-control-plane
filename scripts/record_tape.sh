#!/usr/bin/env bash
# Record a replay tape with the substrate fully alive (DEMO_LOUD on).
#
# Boots the full demo stack via scripts/boot-demo.sh with
# ZAVA_RECORD_TO=$OUT exported, so the FastAPI lifespan attaches a
# Recorder that subscribes to the SAME bus the Functions host + Fleet
# Manager + simulator are firing on. After $DURATION the boot-demo
# process tree is sent SIGTERM and the lifespan teardown finalises the
# tape.
#
# Usage:
#   DURATION=5m OUT=tapes/smoke.tar.gz scripts/record_tape.sh
#   DURATION=30m OUT=tapes/medium.tar.gz scripts/record_tape.sh
#   DURATION=2h  OUT=tapes/landing.tar.gz scripts/record_tape.sh
#
# DURATION accepts: NNs / NNm / NNh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DURATION="${DURATION:-5m}"
OUT="${OUT:?OUT=path/to/tape.tar.gz required}"

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
export ZAVA_RECORD_TO="$OUT"

mkdir -p "$(dirname "$OUT")"
ABS_OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
export ZAVA_RECORD_TO="$ABS_OUT"

echo "[record_tape] DURATION=${DURATION} (${SECS}s) OUT=${ABS_OUT} APP_SHA=${ZAVA_APP_SHA}"
echo "[record_tape] booting full demo stack with recorder attached..."

# Run boot-demo in the background. boot-demo.sh already installs
# `trap cleanup INT TERM EXIT` which kills every child it spawned
# (Azurite, Functions host, FastAPI, vite previews). Sending SIGTERM to
# the boot-demo PID is enough to bring the whole stack down cleanly,
# which also triggers the FastAPI lifespan teardown → Recorder.stop() →
# tape finalisation.
scripts/boot-demo.sh &
BOOT_PID=$!
STOP_REQUESTED=0

cleanup() {
  if [[ -n "${BOOT_PID:-}" ]] && kill -0 "$BOOT_PID" 2>/dev/null; then
    kill -TERM "$BOOT_PID" 2>/dev/null || true
    # Lifespan teardown packs the tarball; FastAPI shutdown for our
    # stack typically completes in <15s. Wait up to 30s before giving
    # up and force-killing the child tree.
    for _ in $(seq 1 30); do
      sleep 1
      kill -0 "$BOOT_PID" 2>/dev/null || break
    done
    kill -9 "$BOOT_PID" 2>/dev/null || true
  fi
}

request_stop() {
  STOP_REQUESTED=1
  cleanup
}
trap request_stop INT TERM

# Wait the requested duration, then ask the demo stack to stop.
sleep "$SECS" || true
echo "[record_tape] duration elapsed; signalling demo stack to finalise tape..."
cleanup

wait "$BOOT_PID" 2>/dev/null || true

if [[ -f "$ABS_OUT" ]]; then
  echo "[record_tape] tape written → $ABS_OUT"
  ls -lh "$ABS_OUT"
else
  echo "[record_tape] WARNING: tape not found at $ABS_OUT" >&2
  exit 1
fi
