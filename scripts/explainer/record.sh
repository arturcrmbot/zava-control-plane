#!/usr/bin/env bash
# record.sh — assemble and run the explainer recorder.
#
# Usage:
#   scripts/explainer/record.sh                 # full recording → dist/video.raw.webm
#   scripts/explainer/record.sh --smoke         # 3-scene smoke → dist/smoke.webm
#   scripts/explainer/record.sh --subset scene-01,scene-03a
#
# Pipeline:
#   1. Read scripts/explainer/scenes.json
#   2. Read scripts/explainer/record.template.js
#   3. Substitute __INLINE_CFG__, __INLINE_SUBSET__, __INLINE_VIDEO_PATH__
#   4. Write dist/record.runtime.js
#   5. Invoke `playwright-cli -s=explainer run-code --filename dist/record.runtime.js`
#
# Browser session must be open first:
#   playwright-cli -s=explainer open --browser=chromium

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

OUT_PATH="dist/video.raw.webm"
SUBSET="[]"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      OUT_PATH="dist/smoke.webm"
      SUBSET='["scene-01","scene-03a","scene-03b"]'
      shift ;;
    --subset)
      OUT_PATH="dist/subset.webm"
      ids="$2"
      SUBSET=$(printf '%s' "$ids" | jq -Rc 'split(",")')
      shift 2 ;;
    --out)
      OUT_PATH="$2"
      shift 2 ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2 ;;
  esac
done

mkdir -p dist

SCENES_JSON=$(cat scripts/explainer/scenes.json)
TEMPLATE=$(cat scripts/explainer/record.template.js)

# Use jq to inject JSON safely (handles quoting/escaping).
python3 - "$SCENES_JSON" "$SUBSET" "$OUT_PATH" <<'PY' > dist/record.runtime.js
import sys, json
scenes_json = sys.argv[1]
subset_json = sys.argv[2]
out_path = sys.argv[3]
with open('scripts/explainer/record.template.js') as f:
    tpl = f.read()
out = (tpl
       .replace('__INLINE_CFG__', scenes_json)
       .replace('__INLINE_SUBSET__', subset_json)
       .replace('__INLINE_VIDEO_PATH__', json.dumps(out_path)))
sys.stdout.write(out)
PY

echo "wrote dist/record.runtime.js ($(wc -c < dist/record.runtime.js) bytes)"
echo "output → $OUT_PATH"
echo "subset → $SUBSET"
echo

exec playwright-cli -s=explainer run-code --filename dist/record.runtime.js
