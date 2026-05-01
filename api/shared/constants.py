# src/shared/constants.py
"""Canonical decision values for HITL approval outcomes + HITL timeouts."""
from __future__ import annotations
from datetime import timedelta

DECISION_APPROVED: frozenset[str] = frozenset({"approve", "approved", "ok"})
DECISION_REJECTED: frozenset[str] = frozenset({"reject", "rejected", "deny", "denied"})

# HITL timeouts for the expense-claim Durable orchestrator. The orchestrator
# yields `wait_for_external_event` against `context.create_timer(...)` using
# these durations; if the timer wins, the workflow short-circuits to a
# timeout-completed status.
JUSTIFICATION_TIMEOUT: timedelta = timedelta(hours=72)
REVIEWER_DECISION_TIMEOUT: timedelta = timedelta(hours=72)

# HITL timeouts for the POC2 hiring orchestrator. Hiring runs over weeks,
# not hours — Finance BP budget approval and HR BP final-offer approval can
# both reasonably sit for several days before timing out.
BUDGET_APPROVAL_TIMEOUT: timedelta = timedelta(days=7)
OFFER_APPROVAL_TIMEOUT: timedelta = timedelta(days=7)

# Phase 6 voice screen — candidate has 24h to walk through the screening
# call link. After the timer wins, the orchestration emits a verdict of
# `timeout` and the candidate must reapply. Mirrors the existing
# wait_for_external_event race-against-timer pattern used elsewhere.
VOICE_SCREEN_TIMEOUT: timedelta = timedelta(hours=24)

# Phase 7 (Interview) sub-wait timeouts.
INTERVIEW_INVITE_TIMEOUT  = timedelta(days=3)   # recruiter to invite/reject
INTERVIEW_BOOKING_TIMEOUT = timedelta(days=7)   # candidate to pick a slot
INTERVIEW_DECISION_TIMEOUT = timedelta(days=5)  # recruiter to record post-int decision
