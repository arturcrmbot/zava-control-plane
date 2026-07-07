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
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import agent_fleet_contract_renewal_market_benchmarker
from api.functions.graphs.executors.validators import validate_fleet_contract_renewal_market_benchmarker_schema


def build_fleet_contract_renewal_market_benchmarker_workflow() -> Workflow:
    return build_linear_workflow([
        ("market_benchmarker", "agent_market_benchmarker", "agent", agent_fleet_contract_renewal_market_benchmarker.execute),
        ("val_market_benchmarker", "validate_fleet_contract_renewal_market_benchmarker_schema", "validator", validate_fleet_contract_renewal_market_benchmarker_schema.execute),
    ])
