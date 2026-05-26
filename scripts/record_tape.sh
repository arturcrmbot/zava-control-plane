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
# IMPORTANT: the dream-pass auto-consolidator DELETES working memories
# when backlog >= threshold. Setting a high threshold so seeded
# memories survive long enough to land in the t=0 snapshot — we
# trigger ONE explicit dream pass below to also produce lessons.
export DREAM_PASS_TRIGGER_BACKLOG=999
export MEMORY_DOMAINS=hiring
export ZAVA_APP_SHA="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
export ZAVA_RECORD_TO="$OUT"
# Default 40s warmup so the t=0 snapshot has seeded workflows AND the
# memory seed batches + explicit dream pass complete BEFORE snapshot.
export ZAVA_RECORD_WARMUP_S="${ZAVA_RECORD_WARMUP_S:-40}"
# Force in-memory FallbackMemory during recording so seeded working
# memories persist even if the Azure OpenAI / GitHub Copilot quota is
# exhausted (Mem0 silently drops writes when its LLM embed calls
# fail). Exported empty so .env's load_dotenv (default override=False)
# leaves it blank rather than re-reading the real endpoint.
export AZURE_OPENAI_ENDPOINT=""
export AZURE_OPENAI_EMBED_DEPLOYMENT=""

mkdir -p "$(dirname "$OUT")"
ABS_OUT="$(cd "$(dirname "$OUT")" && pwd)/$(basename "$OUT")"
export ZAVA_RECORD_TO="$ABS_OUT"

# The recorder only arms AFTER warmup, so extend the boot-demo lifetime
# so the user gets DURATION of actual captured activity.
TOTAL_SECS=$(( SECS + ${ZAVA_RECORD_WARMUP_S%.*} + 5 ))

echo "[record_tape] DURATION=${DURATION} (${SECS}s) WARMUP=${ZAVA_RECORD_WARMUP_S}s OUT=${ABS_OUT} APP_SHA=${ZAVA_APP_SHA}"
echo "[record_tape] booting full demo stack with recorder attached (total runtime: ${TOTAL_SECS}s)..."

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

# After the warmup period, seed realistic working memories so the
# Memory page in replay shows entries even when the LLM-driven agents
# can't run (e.g. GitHub Copilot rate-limited). Uses the same /seed-demo
# endpoint that the dream-pass Playwright E2E uses. Backgrounded so the
# main loop continues the duration countdown.
seed_memories() {
  # Wait for warmup + 3s grace so the Recorder is armed and listening
  # on the bus when memory mutations land.
  sleep "$(( ${ZAVA_RECORD_WARMUP_S%.*} + 3 ))" || return 0
  # Wait for the FastAPI port to actually accept connections.
  for _ in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:3101/api/replay/meta 2>/dev/null | grep -q "^200$"; then
      break
    fi
    sleep 1
  done

  # Round 1: seed batch (will be consumed by the explicit dream pass)
  echo "[record_tape] seeding round 1 memories (for consolidation)..."
  curl -s -X POST http://localhost:3101/api/memory/v2/seed-demo \
    -H "content-type: application/json" \
    -d '{
      "domain": "hiring",
      "entries": [
        {"role":"recruiter","verdict":"reject","gate":"cv_screen","reason":"voice signal weak","signals":{"voice_score":1.2,"cv_score":2},"workflow_id":"W-CV-001"},
        {"role":"recruiter","verdict":"reject","gate":"cv_screen","reason":"voice signal weak","signals":{"voice_score":1.4,"cv_score":1},"workflow_id":"W-CV-002"},
        {"role":"recruiter","verdict":"reject","gate":"cv_screen","reason":"voice signal weak","signals":{"voice_score":1.8,"cv_score":2},"workflow_id":"W-CV-003"},
        {"role":"recruiter","verdict":"reject","gate":"cv_screen","reason":"voice signal weak","signals":{"voice_score":1.1,"cv_score":3},"workflow_id":"W-CV-004"},
        {"role":"recruiter","verdict":"reject","gate":"cv_screen","reason":"voice signal weak","signals":{"voice_score":1.0,"cv_score":2},"workflow_id":"W-CV-005"},
        {"role":"hiring_manager","verdict":"approve","gate":"offer_decision","reason":"strong all-round","signals":{"voice_score":4.5,"cv_score":5},"workflow_id":"W-OFF-101"},
        {"role":"hiring_manager","verdict":"approve","gate":"offer_decision","reason":"strong all-round","signals":{"voice_score":4.7,"cv_score":5},"workflow_id":"W-OFF-102"}
      ]
    }' 2>&1 | head -1
  echo ""

  # Trigger one explicit dream pass to produce lessons
  sleep 2
  echo "[record_tape] triggering dream pass..."
  curl -s -X POST "http://localhost:3101/api/dream-pass/run?domain=hiring" 2>&1 | head -1
  echo ""

  # Round 2: fresh working notes that the consolidator hasn't eaten
  sleep 3
  echo "[record_tape] seeding round 2 memories (fresh working notes)..."
  curl -s -X POST http://localhost:3101/api/memory/v2/seed-demo \
    -H "content-type: application/json" \
    -d '{
      "domain": "hiring",
      "entries": [
        {"role":"recruiter","verdict":"approve","gate":"cv_screen","reason":"strong portfolio","signals":{"voice_score":4.3,"cv_score":5},"workflow_id":"W-CV-LIVE-1"},
        {"role":"talent_lead","verdict":"escalate","gate":"panel_review","reason":"unusual background needs review","signals":{"cv_score":3},"workflow_id":"W-PNL-201"},
        {"role":"hiring_manager","verdict":"approve","gate":"offer_decision","reason":"strong all-round","signals":{"voice_score":4.2,"cv_score":4},"workflow_id":"W-OFF-LIVE-1"}
      ]
    }' 2>&1 | head -1
  echo ""
}
seed_memories &

# Wait the requested duration, then ask the demo stack to stop.
sleep "$TOTAL_SECS" || true
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
