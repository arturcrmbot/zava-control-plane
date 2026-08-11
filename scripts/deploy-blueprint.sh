#!/usr/bin/env bash
# Deploy the public Zava experience as a proof-gated ACA replay.
#
# This is the proof-gated wrapper around the canonical `azure.yaml` deployment
# via `azd up`. It requires ZAVA_MODE=replay, tenant verification,
# proof/manifest.json, proof/seller-review.json, and proof/public-replay.json.
# It deploys the full read-only replay application, not an nginx-only microsite.
#
# Usage:
#   ZAVA_MODE=replay EXPECTED_TENANT_ID=<tenant-id> scripts/deploy-blueprint.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# --------------------------------------------------------------------------
# 1. Verify required commands.
# --------------------------------------------------------------------------
for cmd in az azd git jq uv curl; do
  command -v "$cmd" >/dev/null || {
    echo "ERROR: Missing required command: $cmd" >&2
    exit 2
  }
done

# --------------------------------------------------------------------------
# 2. Require explicit replay mode.
# --------------------------------------------------------------------------
[[ "${ZAVA_MODE:-}" == "replay" ]] || {
  echo "ERROR: Set ZAVA_MODE=replay for the public deployment." >&2
  exit 2
}

# --------------------------------------------------------------------------
# 3. Require tenant isolation env var (set by tenant-isolation process).
# --------------------------------------------------------------------------
[[ -n "${EXPECTED_TENANT_ID:-}" ]] || {
  echo "ERROR: EXPECTED_TENANT_ID is required for tenant isolation." >&2
  exit 2
}

# --------------------------------------------------------------------------
# 4. Require proof artefacts.
# --------------------------------------------------------------------------
for artefact in tapes/demo.tar.gz proof/manifest.json proof/seller-review.json proof/public-replay.json; do
  [[ -f "$artefact" ]] || {
    echo "ERROR: Required proof artefact missing: $artefact" >&2
    exit 2
  }
done

# --------------------------------------------------------------------------
# 5. Optionally enforce clean source via require_clean_source.sh.
# --------------------------------------------------------------------------
if [[ -f tools/lib/require_clean_source.sh ]]; then
  # shellcheck source=/dev/null
  source tools/lib/require_clean_source.sh
  require_clean_source "."
fi

# --------------------------------------------------------------------------
# 6. Verify replay provenance manifest (tape + proof + seller-review + HEAD).
# --------------------------------------------------------------------------
HEAD_SHA="$(git rev-parse HEAD)"
uv run python tools/public_replay_manifest.py verify \
  --source-commit "$HEAD_SHA" \
  --tape tapes/demo.tar.gz \
  --proof proof/manifest.json \
  --seller-review proof/seller-review.json \
  --manifest proof/public-replay.json

# --------------------------------------------------------------------------
# 7. Verify Azure tenant identity before any mutation.
# --------------------------------------------------------------------------
ACTUAL_TENANT_ID="$(az account show --query tenantId -o tsv)"
[[ "$ACTUAL_TENANT_ID" == "$EXPECTED_TENANT_ID" ]] || {
  echo "ERROR: Tenant mismatch: expected $EXPECTED_TENANT_ID, got $ACTUAL_TENANT_ID" >&2
  exit 2
}

# --------------------------------------------------------------------------
# 8. Full ACA deployment via azd.
# --------------------------------------------------------------------------
azd up

# --------------------------------------------------------------------------
# 9. Read the deployed FQDN and smoke-test the live surface.
# --------------------------------------------------------------------------
FQDN="$(azd env get-value AZURE_CONTAINER_APP_FQDN | sed -E 's|^https?://||; s|/$||')"
[[ -n "$FQDN" ]] || {
  echo "ERROR: AZURE_CONTAINER_APP_FQDN is empty after azd env get-value — deployment may have failed." >&2
  exit 2
}

curl -fsS "https://${FQDN}/healthz" >/dev/null

curl -fsS "https://${FQDN}/api/replay/meta" \
  | jq -e '.mode == "replay" and (.recorded_at | type == "string")' >/dev/null

curl -fsS "https://${FQDN}/api/blueprint/composition" \
  | jq -e '.domains | length > 0' >/dev/null

printf '\nPublic replay deployed and verified: https://%s/\n' "$FQDN"
