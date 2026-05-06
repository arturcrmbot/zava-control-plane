#!/usr/bin/env bash
# Smoke test using the .env conn string (the smoke_image_gen.py script
# loads .env in Python so semicolons in conn strings are preserved
# verbatim — bash's `set -a; source` truncates them at the first ;).
set -euo pipefail
cd /Users/arturzielinski/dev/github-repos/wpp-control-plane-poc3-ai-agency
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
exec /Users/arturzielinski/dev/github-repos/wpp-control-plane-poc1/.venv/bin/python tools/scratch/smoke_image_gen.py

