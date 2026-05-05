"""Phase 1 (Op Lookup) graph for Treasury FX domain."""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor


async def _op_lookup_execute(input: dict) -> dict:
    op = input.get("treasury_op") or {}
    op_id = op.get("op_id")
    if not op_id:
        return {"ok": False, "blocked_reason": "missing treasury_op.op_id"}
    return {
        "ok": True,
        "op_id": op_id,
        "op_kind": op.get("op_kind", "spot-hedge"),
        "currency_pair": op.get("currency_pair", "GBP/USD"),
        "notional_gbp": op.get("notional_gbp", 0),
    }


def build_fleet_treasury_fx_op_lookup_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="op_lookup",
        name="deterministic_op_lookup",
        executor_type="deterministic",
        fn=_op_lookup_execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, term)
        .build()
    )
