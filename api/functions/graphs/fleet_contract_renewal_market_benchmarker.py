"""Phase 2 (Market Benchmarker) graph for Contract renewal.

  agent_market_benchmarker -> validate_fleet_contract_renewal_market_benchmarker_schema -> terminal

Per brief: agent benchmarks the contract against three comparable
contracts in our portfolio (same category, similar value band), pulls
fresh market quotes for the category + region, and reviews this
contract's amendment history to surface scope creep. Validator
guardrails the agent payload to the spec shape so Phase 3 can rely on
a stable benchmark band.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_fleet_contract_renewal_market_benchmarker
from api.functions.graphs.executors.validators import validate_fleet_contract_renewal_market_benchmarker_schema


def build_fleet_contract_renewal_market_benchmarker_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="market_benchmarker",
        name="agent_market_benchmarker",
        executor_type="agent",
        fn=agent_fleet_contract_renewal_market_benchmarker.execute,
    )
    n2 = TrackedExecutor(
        id="val_market_benchmarker",
        name="validate_fleet_contract_renewal_market_benchmarker_schema",
        executor_type="validator",
        fn=validate_fleet_contract_renewal_market_benchmarker_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
