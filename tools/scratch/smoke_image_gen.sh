#!/usr/bin/env bash
# Helper to run the image_gen smoke test with a working Azurite conn string.
set -euo pipefail
cd "$(dirname "$0")/../.."
set -a
source .env
set +a
export CREATIVE_REAL_FOUNDRY=1
export CREATIVE_IMAGE_QUALITY=${CREATIVE_IMAGE_QUALITY:-low}
# Azurite needs all 3 endpoints in the conn string (or EndpointSuffix); the
# checked-in .env only carries BlobEndpoint, so override here for the smoke.
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;BlobEndpoint=http://127.0.0.1:10000/devstoreaccount1;QueueEndpoint=http://127.0.0.1:10001/devstoreaccount1;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;"
# The shared venv is editable-installed from poc1. Prepend poc3's worktree
# so `import api.*` picks up the poc3 code rather than poc1's older copy.
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
exec /Users/arturzielinski/dev/github-repos/wpp-control-plane-poc1/.venv/bin/python tools/scratch/smoke_image_gen.py
