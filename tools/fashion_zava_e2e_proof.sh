#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "${ZAVA_VERTICAL:-fashion}" != "fashion" ]]; then
  echo "fashion proof requires ZAVA_VERTICAL=fashion" >&2
  exit 2
fi

exec env ZAVA_VERTICAL=fashion \
  uv run --frozen --no-sync python tools/fashion_zava_e2e_proof.py "$@"

