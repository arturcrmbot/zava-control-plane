#!/usr/bin/env bash
# Autonomous-org profile.
#
# Auto-closes EVERY persona, including recruiter and candidate. Used for
# unattended background runs where we want the steady-state ramp loop to
# produce complete, real workflow walks per domain (so the recorder can
# capture them, etc.).
#
# Do NOT use for live demos with real humans in the room.
#
# Usage:
#   ./scripts/profile-autonomous.sh
#
# This script execs uvicorn so the env var sticks for the FastAPI worker.

set -euo pipefail
cd "$(dirname "$0")/.."

export PERSONA_AUTO_CLOSE="line_manager,claim_submitter,ssc_reviewer,finance_bp,hr_bp,recruiter,candidate"
echo "[profile-autonomous] PERSONA_AUTO_CLOSE=$PERSONA_AUTO_CLOSE"
echo "[profile-autonomous] every persona is AUTO. real humans bypassed."

exec ./.venv/bin/uvicorn api.server.main:app --port 3001 --no-access-log
