"""Phase 3 (Renewal Terms Drafter) graph for Contract renewal.

  agent_renewal_terms_drafter -> validate_fleet_contract_renewal_renewal_terms_drafter_schema -> terminal

Per brief: agent drafts proposed renewal terms by combining the
benchmarked price band with the relevant legal-clause precedents and
proposes a per-line delta vs the current contract. Validator
guardrails the agent payload so the finance persona policy can rely
on `cost_change_pct` being a number.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_contract_renewal_renewal_terms_drafter
from api.functions.graphs.executors.validators import validate_fleet_contract_renewal_renewal_terms_drafter_schema


def build_fleet_contract_renewal_renewal_terms_drafter_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="renewal_terms_drafter",
        name="agent_renewal_terms_drafter",
        executor_type="agent",
        fn=agent_fleet_contract_renewal_renewal_terms_drafter.execute,
    )
    n2 = TrackedExecutor(
        id="val_renewal_terms_drafter",
        name="validate_fleet_contract_renewal_renewal_terms_drafter_schema",
        executor_type="validator",
        fn=validate_fleet_contract_renewal_renewal_terms_drafter_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
