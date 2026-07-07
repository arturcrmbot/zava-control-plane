#!/usr/bin/env bash
# synth.sh — synthesize per-scene WAV from scenes.json using MAI Voice.
#
# Reads scenes.json, synthesizes each scene's text via Azure Speech REST
# (en-US-Grant:MAI-Voice-2), writes audio to dist/audio/<scene-id>.wav, then
# updates scenes.json in place with each scene's measured audio_ms.
#
# Auth: az login under subscription b4b0289a-cba8-45f6-ad48-a9d21908f648
# Cache: scene text sha256 is checked against dist/audio/<scene-id>.sha256;
#        unchanged scenes are skipped.
#
# Requires: az, curl, ffprobe, jq, python3, openssl

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SCENES="$SCRIPT_DIR/scenes.json"
AUDIO_DIR="$REPO_ROOT/dist/audio"

SPEECH_RESOURCE_HOST="azureaiserviceforcontentunderstanding.cognitiveservices.azure.com"
SPEECH_REGION_HOST="swedencentral.tts.speech.microsoft.com"

mkdir -p "$AUDIO_DIR"

echo "==> Switching to MAI Voice subscription"
az account set --subscription b4b0289a-cba8-45f6-ad48-a9d21908f648 >/dev/null

echo "==> Issuing Speech token"
AD_TOKEN="$(az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv)"
SPEECH_TOKEN="$(curl -sf -m 15 -X POST -H "Authorization: Bearer $AD_TOKEN" -H "Content-Length: 0" \
  "https://${SPEECH_RESOURCE_HOST}/sts/v1.0/issueToken")"
[ -n "$SPEECH_TOKEN" ] || { echo "ERROR: empty speech token"; exit 1; }
echo "    speech token length: ${#SPEECH_TOKEN}"

VOICE="$(jq -r '.voice' "$SCENES")"
echo "==> Voice: $VOICE"

# Bump this when SSML wrapper changes so the cache invalidates.
SSML_PROFILE="v3-prosody-rate-plus-10-with-breaks"

# XML-escape text for SSML body, then restore [BREAK:nnn] markers as <break time="nnnms"/>.
xml_escape() {
  python3 -c "
import sys, html, re
t = sys.stdin.read()
t = html.escape(t)
t = re.sub(r'\[BREAK:(\d+)\]', r'<break time=\"\1ms\"/>', t)
print(t, end='')
"
}

SCENE_IDS=($(jq -r '.scenes[].id' "$SCENES"))

for SCENE_ID in "${SCENE_IDS[@]}"; do
  TEXT="$(jq -r --arg id "$SCENE_ID" '.scenes[] | select(.id == $id) | .text' "$SCENES")"
  WAV_PATH="$AUDIO_DIR/${SCENE_ID}.wav"
  SHA_PATH="$AUDIO_DIR/${SCENE_ID}.sha256"
  CURRENT_SHA="$(printf '%s|%s|%s' "$VOICE" "$SSML_PROFILE" "$TEXT" | shasum -a 256 | cut -d' ' -f1)"

  if [ -f "$WAV_PATH" ] && [ -f "$SHA_PATH" ] && [ "$(cat "$SHA_PATH")" = "$CURRENT_SHA" ]; then
    DURATION_MS="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$WAV_PATH" \
      | awk '{ printf "%d", $1 * 1000 }')"
    printf "    [cache] %-15s %5d ms\n" "$SCENE_ID" "$DURATION_MS"
  else
    ESCAPED="$(printf '%s' "$TEXT" | xml_escape)"
    SSML="<speak version='1.0' xml:lang='en-GB'><voice name='${VOICE}'><prosody rate='+10%'>${ESCAPED}</prosody></voice></speak>"

    HTTP_CODE="$(curl -sf -o "$WAV_PATH" -w "%{http_code}" -m 60 -X POST \
      -H "Authorization: Bearer $SPEECH_TOKEN" \
      -H "Content-Type: application/ssml+xml" \
      -H "X-Microsoft-OutputFormat: riff-24khz-16bit-mono-pcm" \
      -H "User-Agent: zava-blueprint-explainer" \
      --data-binary "$SSML" \
      "https://${SPEECH_REGION_HOST}/cognitiveservices/v1" || echo "FAIL")"

    if [ "$HTTP_CODE" != "200" ]; then
      echo "ERROR: synthesis failed for ${SCENE_ID} (HTTP=${HTTP_CODE})"
      head -c 400 "$WAV_PATH" 2>/dev/null
      exit 1
    fi

    echo "$CURRENT_SHA" > "$SHA_PATH"
    DURATION_MS="$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$WAV_PATH" \
      | awk '{ printf "%d", $1 * 1000 }')"
    printf "    [synth] %-15s %5d ms\n" "$SCENE_ID" "$DURATION_MS"
  fi

  # Update scenes.json in place with audio_ms
  jq --arg id "$SCENE_ID" --argjson ms "$DURATION_MS" \
    '(.scenes[] | select(.id == $id) | .audio_ms) = $ms' \
    "$SCENES" > "$SCENES.tmp" && mv "$SCENES.tmp" "$SCENES"
done

TOTAL_MS="$(jq '[.scenes[].audio_ms] | add' "$SCENES")"
echo "==> Total audio duration: $((TOTAL_MS / 1000))s ($((TOTAL_MS / 60000))m$(((TOTAL_MS / 1000) % 60))s)"
