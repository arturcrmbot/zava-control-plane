#!/usr/bin/env bash
# Helper to start the FastAPI control plane for blueprint development.
# Logs to /tmp/fastapi-blueprint.log; backgrounded so the calling shell returns.
set -euo pipefail
cd "$(dirname "$0")/.."
nohup ./.venv/bin/uvicorn api.server.main:app --port 3101 --no-access-log \
  > /tmp/fastapi-blueprint.log 2>&1 &
echo "started pid $!"
