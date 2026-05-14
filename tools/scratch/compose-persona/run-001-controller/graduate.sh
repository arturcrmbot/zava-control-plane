#!/usr/bin/env bash
# graduate.sh — mechanically promote the controller persona generated at this
# run root into the live trees. Re-runnable; idempotent on the SKILL.md copy.
# The registry-entry splice is intentionally manual — printed to stdout for
# the operator to paste into the right per-domain section of personas.py.
set -euo pipefail

RUN_ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$RUN_ROOT/../../../.." && pwd)"
ROLE="controller"

SKILL_SRC="$RUN_ROOT/api/server/personae/$ROLE/SKILL.md"
SKILL_DST="$REPO_ROOT/api/server/personae/$ROLE/SKILL.md"

if [ ! -f "$SKILL_SRC" ]; then
    echo "ERROR: missing SKILL.md at $SKILL_SRC" >&2
    exit 1
fi

mkdir -p "$(dirname "$SKILL_DST")"
cp "$SKILL_SRC" "$SKILL_DST"
echo "wrote $SKILL_DST"

cat <<EOF

  Manual splice required:
  -----------------------
  Open $REPO_ROOT/api/shared/personas.py and paste the entry below
  inside the PERSONAS dict, under the matching domain's comment block.

EOF

cat "$RUN_ROOT/REGISTRY-ENTRY.py"

echo
echo "  Then run: uv run pytest tests/api/shared/test_personas_registry.py"
