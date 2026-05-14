"""Projection: policy_set (autonomous-domain-insights v1, Phase 5.2).

A one-shot workflow spawned when an operator approves a persona's
proposed action. The payload carries:

    decided_on:      list[str]  — node ids the policy targets
    persona_role:    str        — the persona that proposed the action
    verdict:         str        — freeze / unfreeze / cap (or alias)
    attributes:      dict       — expiry_days, scope, ...

The projection records ONE Decision with phase='policy_set' and links
it to every node in decided_on (record_decision shards by kind via
DECIDED_<KIND> rels — see entity_graph.py:_DECIDED_REL_BY_KIND).

Other personae's decision_policy blocks discover the resulting policy
via api.server.services.policy_lookup.active_policies_for(...).
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "policy_set"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    decided_on = tuple(str(x) for x in (p.get("decided_on") or ()))
    persona_role = str(p.get("persona_role") or "")
    attributes = dict(p.get("attributes") or {})
    verdict_override = p.get("verdict")
    decision = build_decision(
        workflow,
        gate_phase="policy_set",
        persona_role=persona_role,
        source_event="persona.action.approved",
        decided_on=decided_on,
        attributes=attributes,
        verdict_override=str(verdict_override) if verdict_override else None,
    )
    return [decision] if decision is not None else []
