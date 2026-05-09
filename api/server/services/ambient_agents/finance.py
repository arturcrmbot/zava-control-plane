"""Ambient agents for the finance function. Declarations land here via compose-domain v4's author-ambient-trigger sub-skill (see plan/feature-agentic-org-phase-2-compose-v4.md)."""
from __future__ import annotations

from api.server.services.ambient_agents import (
    AmbientAgent, BusTrigger, CadenceTrigger, CypherTrigger,
)

# --------------------------------------------------------------------------
# TASK-030 — BudgetVarianceWatcher
# --------------------------------------------------------------------------
# Hourly Cypher sweep over Money(kind='budget-line') nodes whose JSON
# ``attributes`` blob contains a ``variance`` key. When a row is found the
# dispatcher attempts to spawn a ``variance-investigation`` workflow.
#
# NOTE — ``variance-investigation`` is forward-declared. It is NOT yet a
# registered domain in api/shared/domains.py; landing it is a Phase 4
# concern. The dispatcher's ``_spawn_for_agent`` already wraps the spawn
# call in try/except so unknown workflow_types log + skip rather than
# crash the sweep loop. This is intentional.
# --------------------------------------------------------------------------
BudgetVarianceWatcher = AmbientAgent(
    name="budget-variance-watcher",
    function="finance",
    triggers=(CypherTrigger(
        pattern="MATCH (m:Money) WHERE m.kind = 'budget-line' "
                "AND m.attributes CONTAINS '\"variance\"' "
                "RETURN m LIMIT 100",
        sweep_seconds=3600,
    ),),
    reasoning_skill=None,
    spawnable_workflow_types=("variance-investigation",),
)


# --------------------------------------------------------------------------
# TASK-031 — VendorRiskWatcher
# --------------------------------------------------------------------------
# Daily Cypher sweep over high-risk vendor Organisations. Spawns a
# ``vendor-kyc`` re-screen workflow per matched vendor.
# --------------------------------------------------------------------------
VendorRiskWatcher = AmbientAgent(
    name="vendor-risk-watcher",
    function="finance",
    triggers=(CypherTrigger(
        pattern="MATCH (o:Organisation) WHERE o.kind = 'vendor' "
                "AND o.risk_band = 'high' RETURN o LIMIT 100",
        sweep_seconds=86400,
    ),),
    reasoning_skill=None,
    spawnable_workflow_types=("vendor-kyc",),
)
