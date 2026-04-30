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
