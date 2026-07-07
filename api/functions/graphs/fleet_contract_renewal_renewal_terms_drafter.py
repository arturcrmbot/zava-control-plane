"""Phase 3 (Renewal Terms Drafter) graph for Contract renewal.

  agent_renewal_terms_drafter -> validate_fleet_contract_renewal_renewal_terms_drafter_schema -> terminal

Per brief: agent drafts proposed renewal terms by combining the
benchmarked price band with the relevant legal-clause precedents and
proposes a per-line delta vs the current contract. Validator
guardrails the agent payload so the finance persona policy can rely
on `cost_change_pct` being a number.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_contract_renewal_renewal_terms_drafter
from api.functions.graphs.executors.validators import validate_fleet_contract_renewal_renewal_terms_drafter_schema


def build_fleet_contract_renewal_renewal_terms_drafter_workflow() -> Workflow:
    return build_linear_workflow([
        ("renewal_terms_drafter", "agent_renewal_terms_drafter", "agent", agent_fleet_contract_renewal_renewal_terms_drafter.execute),
        ("val_renewal_terms_drafter", "validate_fleet_contract_renewal_renewal_terms_drafter_schema", "validator", validate_fleet_contract_renewal_renewal_terms_drafter_schema.execute),
    ])
