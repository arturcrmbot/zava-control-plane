#!/usr/bin/env bash
# Friday demo profile.
#
# Auto-closes back-office personae (Travel line manager, Expense submitter +
# SSC reviewer, Hiring Finance BP + HR BP) so the workflows progress.
#
# Leaves recruiter and candidate as REAL HUMANS — they drive the
# hiring workflow via the recruiter UI and the candidate portal.
#
# Usage:
#   ./scripts/profile-friday.sh
#
# This script execs uvicorn so the env var sticks for the FastAPI worker.

set -euo pipefail
cd "$(dirname "$0")/.."

export PERSONA_AUTO_CLOSE="line_manager,claim_submitter,ssc_reviewer,finance_bp,hr_bp"
echo "[profile-friday] PERSONA_AUTO_CLOSE=$PERSONA_AUTO_CLOSE"
echo "[profile-friday] recruiter and candidate stay HUMAN — drive via portal."

exec ./.venv/bin/uvicorn api.server.main:app --port 3001 --no-access-log
