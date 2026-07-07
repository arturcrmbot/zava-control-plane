"""Phase 1 (Contract Lookup) graph for Contract renewal.

  deterministic_contract_lookup -> terminal

Per brief: read the contract record (parties, value, term, category,
region) from the contract repository. Pass forward. No agent, no
validator — just a deterministic call that produces the canonical phase
output shape so downstream phases (and the personae) can read the
contract's current annual value, category and region from a single dict.
"""
from __future__ import annotations
from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.server.mcp_tools.contract_repository import get_contract


async def _contract_lookup_execute(input: dict) -> dict:
    """Deterministic contract lookup. Reads `contract.contract_id` from the
    orchestrator payload, calls the contract_repository MCP tool directly
    (no agent session — pure I/O), returns the structured record."""
    contract = input.get("contract") or {}
    contract_id = contract.get("contract_id")
    if not contract_id:
        return {"ok": False, "blocked_reason": "missing contract.contract_id"}
    record = get_contract(contract_id)
    return {
        "ok": True,
        "contract_id": record["contract_id"],
        "vendor": record["vendor"],
        "counterparty": record["counterparty"],
        "category": record["category"],
        "region": record["region"],
        "current_annual_value_usd": record["current_annual_value_usd"],
        "term_years": record["term_years"],
        "expires_on": record["expires_on"],
        "owner_employee_id": record["owner_employee_id"],
    }


def build_fleet_contract_renewal_contract_lookup_workflow() -> Workflow:
    return build_linear_workflow([
        ("contract_lookup", "deterministic_contract_lookup", "deterministic", _contract_lookup_execute),
    ])
