# src/functions/graphs/arbitrate.py
"""Phase 6 (Arbitrate) graph for expense claims.

  agent_arbitration -> validate_arbitration_schema -> terminal

Per spec §4.1 Phase 6: SSC reviewer arbitration on Red claims after the
claimant justification round-trip from Phase 5. Recommends one of
accept-justification / require-repayment / issue-warning / escalate
with a cited precedent.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_arbitration
from api.functions.graphs.executors.validators import validate_arbitration_schema


def build_arbitrate_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="arbitration",
        name="agent_arbitration",
        executor_type="agent",
        fn=agent_arbitration.execute,
    )
    n2 = TrackedExecutor(
        id="val_arb_schema",
        name="validate_arbitration_schema",
        executor_type="validator",
        fn=validate_arbitration_schema.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
