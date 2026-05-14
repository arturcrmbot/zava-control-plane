#!/usr/bin/env bash
# Deploy the blueprint microsite to Azure Container Apps.
#
# Idempotent. First run provisions ACR + Container Apps environment.
# Subsequent runs build a fresh image and update the running container.
#
# Usage:
#   scripts/deploy-blueprint.sh
#
# Override defaults via env vars:
#   RG=...           override resource group  (default: zava-control-plane-demo)
#   LOCATION=...     override region          (default: swedencentral)
#   APP_NAME=...     override container app   (default: blueprint)
#   ENV_NAME=...     override environment     (default: blueprint-env)
#   ACR_NAME=...     override ACR name        (default: blueprintacrzavademo)

set -euo pipefail

RG="${RG:-zava-control-plane-demo}"
LOCATION="${LOCATION:-swedencentral}"
APP_NAME="${APP_NAME:-blueprint}"
ENV_NAME="${ENV_NAME:-blueprint-env}"
# ACR names: 5-50 lowercase alphanumeric chars. Use a short deterministic
# name so re-runs find the same registry.
ACR_NAME="${ACR_NAME:-blueprintacrzavademo}"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"

cd "$(dirname "$0")/.."

echo "==> Subscription: $(az account show --query name -o tsv)"
echo "==> Target:       $APP_NAME in $RG ($LOCATION)"
echo "==> ACR:          $ACR_NAME"
echo "==> Image tag:    $IMAGE_TAG"
echo ""

# --------------------------------------------------------------------------
# 1. Ensure ACR exists.
# --------------------------------------------------------------------------
if ! az acr show --name "$ACR_NAME" --resource-group "$RG" >/dev/null 2>&1; then
    echo "==> Creating ACR $ACR_NAME ..."
    az acr create \
        --resource-group "$RG" \
        --name "$ACR_NAME" \
        --sku Basic \
        --location "$LOCATION" \
        --admin-enabled true \
        >/dev/null
fi

LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer -o tsv)
echo "==> Login server: $LOGIN_SERVER"

# --------------------------------------------------------------------------
# 2. Build the image in ACR (no local Docker required).
# --------------------------------------------------------------------------
echo ""
echo "==> Building image in ACR (this is the slow step) ..."
az acr build \
    --registry "$ACR_NAME" \
    --resource-group "$RG" \
    --image "blueprint:${IMAGE_TAG}" \
    --image "blueprint:latest" \
    --file web/blueprint/Dockerfile \
    .

# --------------------------------------------------------------------------
# 3. Ensure Container Apps environment exists.
# --------------------------------------------------------------------------
if ! az containerapp env show --name "$ENV_NAME" --resource-group "$RG" >/dev/null 2>&1; then
    echo ""
    echo "==> Creating Container Apps environment $ENV_NAME ..."
    az containerapp env create \
        --name "$ENV_NAME" \
        --resource-group "$RG" \
        --location "$LOCATION" \
        >/dev/null
fi

# --------------------------------------------------------------------------
# 4. Create or update the container app.
# --------------------------------------------------------------------------
ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username -o tsv)
ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" -o tsv)
IMAGE="${LOGIN_SERVER}/blueprint:${IMAGE_TAG}"

if az containerapp show --name "$APP_NAME" --resource-group "$RG" >/dev/null 2>&1; then
    echo ""
    echo "==> Updating existing container app $APP_NAME with image $IMAGE ..."
    az containerapp update \
        --name "$APP_NAME" \
        --resource-group "$RG" \
        --image "$IMAGE" \
        --set-env-vars BLUEPRINT_AUTOSTART_STREAM=1 \
        >/dev/null
else
    echo ""
    echo "==> Creating container app $APP_NAME ..."
    az containerapp create \
        --name "$APP_NAME" \
        --resource-group "$RG" \
        --environment "$ENV_NAME" \
        --image "$IMAGE" \
        --target-port 80 \
        --ingress external \
        --registry-server "$LOGIN_SERVER" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --cpu 0.5 --memory 1Gi \
        --min-replicas 0 --max-replicas 1 \
        --env-vars BLUEPRINT_AUTOSTART_STREAM=1 \
        >/dev/null
fi

echo ""
echo "==> Done. Resolving FQDN ..."
FQDN=$(az containerapp show --name "$APP_NAME" --resource-group "$RG" \
    --query properties.configuration.ingress.fqdn -o tsv)

echo ""
echo "  https://$FQDN"
echo ""
echo "Smoke-test:"
echo "  curl -s https://$FQDN/api/health"
echo "  curl -s https://$FQDN/api/blueprint/composition | python3 -m json.tool | head -20"
