#!/usr/bin/env bash
# Runs once when the Codespace / devcontainer is created.
set -euo pipefail

echo "==> installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
# Make uv available immediately in this shell + every future one
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"

echo "==> installing azure-functions-core-tools@4.9.0 (global)"
sudo npm install -g azure-functions-core-tools@4.9.0 --unsafe-perm true
func --version

echo "==> uv sync (control-plane-py)"
(cd control-plane-py && uv sync)

echo "==> local.settings.json (from template if missing)"
[ -f control-plane-py/local.settings.json ] || \
  cp control-plane-py/local.settings.json.example control-plane-py/local.settings.json

echo "==> .env (from template if missing)"
[ -f control-plane-py/.env ] || cp control-plane-py/.env.example control-plane-py/.env

echo "==> npm install (control-plane UI)"
(cd control-plane && npm install)

echo ""
echo "Setup complete. Run 'make up' from control-plane-py/ to boot."
echo "The UI will auto-open on the forwarded port."
