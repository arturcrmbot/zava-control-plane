#!/usr/bin/env bash
# Stops every process `make up` (boot-demo.sh) starts.
#
# `boot-demo.sh` registers a TERM/INT trap, but `func host start` runs in
# its own process group and survives Ctrl-C of the parent bash. Same for
# `tsx mocks/*-mcp/server.ts` under `concurrently`. This script catches
# all of them by command-line substring, so a stale invocation can't keep
# port 7071 / 3101 / 5273-5275 / 10000-10002 / 4101-4103 / 4108 bound and
# block the next `make up`.
#
# Idempotent: returns 0 even when nothing matches.

set -u

patterns=(
  "uvicorn api.server.main"          # FastAPI
  "func host start"                  # Azure Functions host (.NET wrapper)
  "Microsoft.Azure.Functions"        # Functions worker
  "azure-functions-core-tools/bin/workers/python"  # Python Functions worker (orphans on host exit)
  "func\$"                            # bare func binary, edge case
  "vite preview"                     # built-bundle UI servers (5273/5274/5275)
  "azurite"                          # storage emulator
  "concurrently.*tsx mocks"          # mock-MCP umbrella
  "tsx mocks/.*-mcp/server"          # individual mocks (workday/concur/maconomy/authority)
  "boot-demo.sh"                     # the orchestrator itself
)

for pat in "${patterns[@]}"; do
  pkill -f "$pat" 2>/dev/null || true
done

# Laya only if boot-demo started it (it frees ~3 GB). A Laya started by hand,
# or serving other work, is left running.
laya_pid_file="$(cd "$(dirname "$0")/.." && pwd)/.compose/laya.pid"
if [[ -f "$laya_pid_file" ]]; then
  kill "$(cat "$laya_pid_file")" 2>/dev/null || true
  rm -f "$laya_pid_file"
fi

# Give children a moment to drain, then SIGKILL anything still bound to
# our well-known ports (last-resort safety net).
sleep 2
for port in 7071 3101 5273 5274 5275 10000 10001 10002 4101 4102 4103 4108; do
  pids=$(lsof -nP -ti:"$port" 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    kill -9 $pids 2>/dev/null || true
  fi
done

# A dying Functions host can spawn one more Python worker after the first
# sweep; it orphans and keeps the vertical's stores locked. Sweep again.
sleep 1
pkill -f "azure-functions-core-tools/bin/workers/python" 2>/dev/null || true

echo "[down] all known demo processes stopped"
