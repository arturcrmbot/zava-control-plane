# src/functions/graphs/reconciliation.py
"""
Reconciliation graph (hybrid):
  bank_statement_match -> [if unmatched_items empty, terminal]
                       -> agent_exception_classifier -> agent_root_cause_explainer
                       -> agent_resolution_recommender -> validate_recommendation_authority
                       -> terminal

For v1 simplicity, the agent chain runs but only processes the first unmatched_item.
If the list is empty, the agent calls degrade gracefully (skill returns parse_error: True
for missing context). Demo screenshots focus on the deterministic-only path.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from src.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from src.functions.graphs.executors.deterministic import bank_statement_match
from src.functions.graphs.executors.agents import (
    agent_exception_classifier, agent_root_cause_explainer, agent_resolution_recommender,
)
from src.functions.graphs.executors.validators import validate_recommendation_authority


async def first_unmatched_or_skip(input: dict) -> dict:
    """If there are no unmatched items, mark the graph as 'recon-clean' and short-circuit."""
    if not input.get("unmatched_items"):
        return {"recon_clean": True, "unmatched_item": None}
    return {"unmatched_item": input["unmatched_items"][0]}


def build_reconciliation_workflow() -> Workflow:
    n1 = TrackedExecutor(id="bank_match", name="bank_statement_match",
                         executor_type="deterministic", fn=bank_statement_match.execute)
    n2 = TrackedExecutor(id="pick_first", name="first_unmatched_or_skip",
                         executor_type="deterministic", fn=first_unmatched_or_skip)
    n3 = TrackedExecutor(id="exc_class", name="agent_exception_classifier",
                         executor_type="agent", fn=agent_exception_classifier.execute)
    n4 = TrackedExecutor(id="root_cause", name="agent_root_cause_explainer",
                         executor_type="agent", fn=agent_root_cause_explainer.execute)
    n5 = TrackedExecutor(id="resolution", name="agent_resolution_recommender",
                         executor_type="agent", fn=agent_resolution_recommender.execute)
    n6 = TrackedExecutor(id="val_auth", name="validate_recommendation_authority",
                         executor_type="validator", fn=validate_recommendation_authority.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2).add_edge(n2, n3)
        .add_edge(n3, n4).add_edge(n4, n5)
        .add_edge(n5, n6).add_edge(n6, term)
        .build()
    )
