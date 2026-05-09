"""Ambient agents for the tech function. Declarations land here via compose-domain v4's author-ambient-trigger sub-skill (see plan/feature-agentic-org-phase-2-compose-v4.md)."""
from __future__ import annotations

from api.server.services.ambient_agents import (
    AmbientAgent, BusTrigger, CadenceTrigger, CypherTrigger,
)

# --------------------------------------------------------------------------
# TASK-032 — AccessAnomalyWatcher
# --------------------------------------------------------------------------
# Bus-triggered: when an it-access-request workflow completes with an
# 'approved' verdict, spawn an ``access-review`` follow-up workflow.
#
# NOTE — ``access-review`` is forward-declared and not yet a registered
# domain. The dispatcher's ``_spawn_for_agent`` logs + skips on unknown
# workflow_types; landing the access-review domain is a Phase 4 concern.
# --------------------------------------------------------------------------
AccessAnomalyWatcher = AmbientAgent(
    name="access-anomaly-watcher",
    function="tech",
    triggers=(BusTrigger(
        event_type="workflow.completed",
        filter="payload.get('workflow_type') == 'it-access-request' "
               "and payload.get('decision_outcome', {}).get('verdict') == 'approved'",
    ),),
    reasoning_skill=None,
    spawnable_workflow_types=("access-review",),
)
