#!/usr/bin/env bash
# mux.sh — concat scene audio + overlay onto recorded video.
#
# Usage:
#   scripts/explainer/mux.sh                                    # full → dist/agentic-blueprint-explainer.mp4
#   scripts/explainer/mux.sh --smoke                            # smoke → dist/smoke.mp4
#   scripts/explainer/mux.sh --video FILE --subset id1,id2 --out FILE
#
# Pipeline:
#   1. Build per-subset audio concat list (in scenes.json order)
#   2. ffmpeg concat WAVs → dist/audio.wav
#   3. ffmpeg mux video.webm + audio.wav at 30fps CFR, H.264 + AAC, -shortest

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

VIDEO="dist/video.raw.webm"
OUT="dist/agentic-blueprint-explainer.mp4"
SUBSET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --smoke)
      VIDEO="dist/smoke.webm"
      OUT="dist/smoke.mp4"
      SUBSET="scene-01,scene-03a,scene-03b"
      shift ;;
    --video)  VIDEO="$2"; shift 2 ;;
    --subset) SUBSET="$2"; shift 2 ;;
    --out)    OUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$VIDEO" ]] || { echo "missing video: $VIDEO" >&2; exit 1; }

CONCAT_LIST="dist/audio-concat.txt"
AUDIO_OUT="dist/audio.wav"
GAP_WAV="dist/audio/_gap-700ms.wav"

# 700ms of silence at 24kHz mono PCM — matches scene WAV format so concat
# can pass-through without re-encoding. Created once, cached forever.
if [[ ! -f "$GAP_WAV" ]]; then
  mkdir -p "$(dirname "$GAP_WAV")"
  ffmpeg -y -loglevel error \
    -f lavfi -i "anullsrc=channel_layout=mono:sample_rate=24000" \
    -t 0.7 -c:a pcm_s16le "$GAP_WAV"
fi

python3 - "$SUBSET" > "$CONCAT_LIST" <<'PY'
import sys, json, os
subset = [s for s in sys.argv[1].split(',') if s] if len(sys.argv) > 1 and sys.argv[1] else None
scenes = json.load(open('scripts/explainer/scenes.json'))['scenes']
if subset:
    scenes = [s for s in scenes if s['id'] in subset]
gap = os.path.abspath(os.path.join('dist', 'audio', '_gap-700ms.wav'))
for i, s in enumerate(scenes):
    p = os.path.join('dist', 'audio', f"{s['id']}.wav")
    assert os.path.exists(p), f"missing audio: {p}"
    sys.stdout.write(f"file '{os.path.abspath(p)}'\n")
    # Insert a 700ms breath between scenes (not after the last).
    if i < len(scenes) - 1:
        sys.stdout.write(f"file '{gap}'\n")
PY

echo "audio concat list:"
cat "$CONCAT_LIST"
echo

ffmpeg -y -loglevel error -f concat -safe 0 -i "$CONCAT_LIST" -c copy "$AUDIO_OUT"
echo "audio → $AUDIO_OUT"

ffmpeg -y -loglevel error \
  -i "$VIDEO" -i "$AUDIO_OUT" \
  -map 0:v -map 1:a \
  -filter:v "fps=30,tpad=stop_mode=clone:stop_duration=30" \
  -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -shortest \
  -movflags +faststart \
  "$OUT"

echo
echo "→ $OUT"
ffprobe -v error -show_entries format=duration,size:stream=width,height,codec_name -of default=noprint_wrappers=1 "$OUT"
