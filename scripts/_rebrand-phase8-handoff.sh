#!/usr/bin/env bash
# Phase 8 handoff — folder rename + venv rebuild + GitHub repo rename + origin update
#
# Run this AFTER closing the VS Code window that has the old wpp-control-plane-poc1
# workspace open. VS Code holds file watchers on the workspace directory, so the
# `mv` will fail or leave VS Code in a confused state if you don't close it first.
#
# Run from a fresh terminal (Terminal.app, iTerm, etc) — NOT from inside VS Code.
#
# Steps:
#   1. mv ~/dev/github-repos/wpp-control-plane-poc1 → ~/dev/github-repos/zava-control-plane-poc1
#   2. Recreate the .venv (its bin shebangs hard-code the old absolute path)
#   3. Rename the GitHub repo arturcrmbot/wpp-control-plane-poc1 → zava-control-plane-poc1
#      (GitHub auto-redirects old clone URLs indefinitely)
#   4. Update local git origin to the new GitHub URL
#   5. Open VS Code at the new path

set -euo pipefail

OLD_DIR="$HOME/dev/github-repos/wpp-control-plane-poc1"
NEW_DIR="$HOME/dev/github-repos/zava-control-plane-poc1"
OLD_REPO_NAME="wpp-control-plane-poc1"
NEW_REPO_NAME="zava-control-plane-poc1"
GH_OWNER="arturcrmbot"

echo "==> Pre-flight checks ..."
[[ -d "$OLD_DIR" ]] || { echo "ERROR: $OLD_DIR does not exist."; exit 1; }
[[ ! -d "$NEW_DIR" ]] || { echo "ERROR: $NEW_DIR already exists. Aborting."; exit 1; }
command -v gh >/dev/null || { echo "ERROR: gh CLI not found."; exit 1; }
command -v uv >/dev/null || { echo "ERROR: uv not found (need it to recreate venv)."; exit 1; }

# Verify VS Code isn't holding the directory.
if pgrep -f "Visual Studio Code" >/dev/null && lsof +D "$OLD_DIR" 2>/dev/null | grep -q "Code Helper"; then
    echo "ERROR: VS Code is still holding files in $OLD_DIR. Close it first."
    exit 1
fi

echo ""
echo "==> Step 1/5: mv folder ..."
mv "$OLD_DIR" "$NEW_DIR"
echo "   Done."

cd "$NEW_DIR"

echo ""
echo "==> Step 2/5: Keep old venv as backup, build new one ..."
mv .venv .venv.old
uv venv .venv
# uv pip install with the renamed path — re-installs the package as zava-control-plane-py.
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e . --no-deps
echo "   Done. Old venv at .venv.old (delete after verifying)."

echo ""
echo "==> Step 3/5: Rename GitHub repo ${GH_OWNER}/${OLD_REPO_NAME} → ${NEW_REPO_NAME} ..."
gh repo rename "$NEW_REPO_NAME" --repo "${GH_OWNER}/${OLD_REPO_NAME}" --yes
echo "   Done. GitHub auto-creates a redirect from old URL."

echo ""
echo "==> Step 4/5: Update local git origin ..."
git remote set-url origin "https://github.com/${GH_OWNER}/${NEW_REPO_NAME}.git"
git remote -v
echo "   Done."

echo ""
echo "==> Step 5/5: Verify venv + tests ..."
make test 2>&1 | tail -3 || echo "(test failures — review before committing)"

echo ""
echo "==> All done. Reopen VS Code at the new path:"
echo "   code $NEW_DIR"
echo ""
echo "After verifying everything works:"
echo "   rm -rf $NEW_DIR/.venv.old"
echo ""
echo "And in 7 days (CON-005), schedule old Azure RG cleanup:"
echo "   az group delete -n project-apex-demo --yes --no-wait"
