#!/usr/bin/env bash
# Build the blueprint image in ACR. No-frills wrapper to avoid shell
# quoting headaches in chat-driven runs.
set -euo pipefail
cd "$(dirname "$0")/.."
exec az acr build \
    --registry blueprintacrapexdemo \
    --resource-group project-apex-demo \
    --image blueprint:test2 \
    --image blueprint:latest \
    --file web/blueprint/Dockerfile \
    .
