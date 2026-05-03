#!/usr/bin/env bash
# Build the blueprint image in ACR AND roll the Container App revision.
#
# This script does the full deploy. ACR Container Apps caches the :latest
# tag and won't pick up a new push unless you swap to an immutable
# reference (digest or unique tag). We do both: tag with a timestamp,
# tag :latest for convenience, then `containerapp update` against the
# digest of the new push so a fresh revision spins.
set -euo pipefail
cd "$(dirname "$0")/.."

REGISTRY="${REGISTRY:-blueprintacrapexdemo}"
RG="${RG:-project-apex-demo}"
APP_NAME="${APP_NAME:-blueprint}"
TAG="$(date -u +%Y%m%d-%H%M%S)"

echo "==> Building blueprint:$TAG (and :latest) in $REGISTRY"
az acr build \
    --registry "$REGISTRY" \
    --resource-group "$RG" \
    --image "blueprint:$TAG" \
    --image "blueprint:latest" \
    --file web/blueprint/Dockerfile \
    .

echo "==> Resolving digest of blueprint:$TAG"
DIGEST=$(az acr repository show \
    --name "$REGISTRY" \
    --image "blueprint:$TAG" \
    --query digest -o tsv)
IMAGE_REF="${REGISTRY}.azurecr.io/blueprint@${DIGEST}"

echo "==> Rolling $APP_NAME to $IMAGE_REF"
az containerapp update \
    --name "$APP_NAME" \
    --resource-group "$RG" \
    --image "$IMAGE_REF" >/dev/null

echo "==> Done. New revision is live."
echo "    https://blueprint.jollystone-c036938d.swedencentral.azurecontainerapps.io/"
