"""Ambient agents for the hr function. Declarations land here via compose-domain v4's author-ambient-trigger sub-skill (see plan/feature-agentic-org-phase-2-compose-v4.md)."""
from __future__ import annotations

from api.server.services.ambient_agents import (
    AmbientAgent, BusTrigger, CadenceTrigger, CypherTrigger,
)

# Phase 6 (TASK-035..-037) plants concrete declarations here. Until
# then this module exposes no agent symbols.

# --------------------------------------------------------------------------
# Phase 4 IP1 (TASK-006b) — MorningSweep
# --------------------------------------------------------------------------
# Cross-function daily brief, fired weekdays at 09:00 by the cadence
# loop. Pure reasoning skill (no spawnable workflow_types) — produces
# the morning brief from real KPI + decision data.
# --------------------------------------------------------------------------
MorningSweep = AmbientAgent(
    name="morning-sweep",
    function="hr",
    triggers=(CadenceTrigger(cron="0 9 * * 1-5"),),
    reasoning_skill="cross-function-daily-brief",
    spawnable_workflow_types=(),
)
