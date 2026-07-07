#!/usr/bin/env bash
# Supervised restart of the Functions host + API so a freshly graduated domain
# goes live. Detached from the API it restarts. Localhost/demo only.
set -euo pipefail
cd "${ZAVA_REPO_ROOT:-$PWD}"
source scripts/lib/compose-start.sh

stop_pid "$PIDDIR/func.pid"
stop_pid "$PIDDIR/api.pid"
sleep 2
start_func
sleep 3
start_api
echo "compose-ignite: restarted func + api"
