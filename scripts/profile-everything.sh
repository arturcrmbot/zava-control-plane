#!/usr/bin/env bash
# Demo finale profile — turn the whole substrate on.
#
# After the operator has walked through POC1 (one expense claim per minute)
# and POC2 (manual /apply → triage → screen → offer), source this file in
# the boot terminal to flip every domain on with autonomous personae.
#
# This does NOT restart the stack. It exports the new env vars and tells
# you how to apply them.
#
# Usage:
#   source scripts/profile-everything.sh
#   # then either:
#   #   - restart `make up` in a fresh terminal so the new env wins, OR
#   #   - hot-flip just the simulator + persona env without rebooting:
#       curl -s -X POST http://localhost:3001/api/simulator/inject -d '{}'  # POC1 spike

export SIMULATOR_RAMP_ENABLED=1
export SIMULATOR_RAMP_AVG_INTERVAL_SECONDS=25
unset  SIMULATOR_RAMP_DOMAINS    # all live domains

export PORTAL_SEED_REQS=1

export PERSONA_AUTO_CLOSE="line_manager,claim_submitter,ssc_reviewer,finance_bp,hr_bp,recruiter,candidate,onboarding_it_admin,vendor_kyc_finance_bp,it_access_line_manager,it_access_it_admin,contract_finance_bp,contract_line_manager,perf_review_hr_bp,perf_review_line_manager,ap_clerk,controller,category_manager,sourcing_lead,cpo,contracts_counsel,gc,dpo,treasurer,cfo,finance_controller"

echo "[profile-everything] every domain ramps; every persona auto-decides."
echo "[profile-everything] SIMULATOR_RAMP_DOMAINS=<all>  AVG_INTERVAL=${SIMULATOR_RAMP_AVG_INTERVAL_SECONDS}s"
echo "[profile-everything] PORTAL_SEED_REQS=1  PERSONA_AUTO_CLOSE=<full set>"
echo ""
echo "Stop the current stack (Ctrl-C in the make terminal) and re-run 'make up'"
echo "in this same shell to pick up the new env."
