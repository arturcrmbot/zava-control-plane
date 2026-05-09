"""Ambient agents for the ceo function. Phase 4 IP1 (TASK-006b)."""
from __future__ import annotations

from api.server.services.ambient_agents import AmbientAgent, CadenceTrigger


# --------------------------------------------------------------------------
# Phase 4 IP1 (TASK-006b) — QuarterlyOkr
# --------------------------------------------------------------------------
# Quarterly OKR review, fired on the 1st of Jan/Apr/Jul/Oct at 08:00
# by the cadence loop. Reasoning-skill driven; no workflow spawn.
# --------------------------------------------------------------------------
QuarterlyOkr = AmbientAgent(
    name="quarterly-okr",
    function="ceo",
    triggers=(CadenceTrigger(cron="0 8 1 1,4,7,10 *"),),
    reasoning_skill="okr-quarterly-review",
    spawnable_workflow_types=(),
)
