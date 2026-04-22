# src/functions/graphs/routing.py
"""
Routing graph (hybrid, GL coding & cost centre):
  lookup_vendor_context -> lookup_active_gls -> lookup_cost_centre_policy
    -> agent_invoice_classifier -> agent_gl_coder -> agent_cost_centre_assigner
    -> validate_gl_active -> validate_threshold_authority -> record_decision
    -> terminal

Note: spec calls for parallel fan-out at the start. For v1 we run sequentially -- output
is identical because merges are commutative in our dict shape, and parallel adds
WorkflowBuilder edge-group complexity that doesn't affect demo screenshots.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.deterministic import (
    lookup_vendor_context, lookup_active_gls, lookup_cost_centre_policy, record_decision,
)
from api.functions.graphs.executors.agents import (
    agent_invoice_classifier, agent_gl_coder, agent_cost_centre_assigner,
)
from api.functions.graphs.executors.validators import (
    validate_gl_active, validate_threshold_authority,
)


def build_routing_workflow() -> Workflow:
    n1 = TrackedExecutor(id="lookup_vendor", name="lookup_vendor_context",
                         executor_type="deterministic", fn=lookup_vendor_context.execute)
    n2 = TrackedExecutor(id="lookup_gls", name="lookup_active_gls",
                         executor_type="deterministic", fn=lookup_active_gls.execute)
    n3 = TrackedExecutor(id="lookup_cc", name="lookup_cost_centre_policy",
                         executor_type="deterministic", fn=lookup_cost_centre_policy.execute)
    n4 = TrackedExecutor(id="classifier", name="agent_invoice_classifier",
                         executor_type="agent", fn=agent_invoice_classifier.execute)
    n5 = TrackedExecutor(id="gl_coder", name="agent_gl_coder",
                         executor_type="agent", fn=agent_gl_coder.execute)
    n6 = TrackedExecutor(id="cc_assigner", name="agent_cost_centre_assigner",
                         executor_type="agent", fn=agent_cost_centre_assigner.execute)
    n7 = TrackedExecutor(id="val_gl", name="validate_gl_active",
                         executor_type="validator", fn=validate_gl_active.execute)
    n8 = TrackedExecutor(id="val_thr", name="validate_threshold_authority",
                         executor_type="validator", fn=validate_threshold_authority.execute)
    n9 = TrackedExecutor(id="record", name="record_decision",
                         executor_type="deterministic", fn=record_decision.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2).add_edge(n2, n3).add_edge(n3, n4)
        .add_edge(n4, n5).add_edge(n5, n6)
        .add_edge(n6, n7).add_edge(n7, n8).add_edge(n8, n9)
        .add_edge(n9, term)
        .build()
    )
