#!/usr/bin/env bash
# Continuously fire blueprint observatory events for the live demo. Alternates
# hire-walk and expense-walk every TICK_SECONDS (default 20s). Logs to
# /tmp/blueprint-ticker.log so the page can be watched in the browser without
# a noisy terminal in front of it.
#
# Stop with: pkill -f blueprint-ticker.sh
set -euo pipefail
TICK_SECONDS="${TICK_SECONDS:-20}"
URL="http://localhost:3101/api/blueprint/_demo_emit"
SCRIPTS=("hire-walk" "expense-walk")
i=0
while true; do
  script="${SCRIPTS[$((i % 2))]}"
  ts="$(date +%H:%M:%S)"
  if curl -s -X POST "$URL?script=$script&interval_ms=350" -o /dev/null -w "%{http_code}" > /tmp/blueprint-ticker-status; then
    code="$(cat /tmp/blueprint-ticker-status)"
    echo "$ts  $script  -> HTTP $code" >> /tmp/blueprint-ticker.log
  else
    echo "$ts  $script  -> request failed" >> /tmp/blueprint-ticker.log
  fi
  i=$((i + 1))
  sleep "$TICK_SECONDS"
done
