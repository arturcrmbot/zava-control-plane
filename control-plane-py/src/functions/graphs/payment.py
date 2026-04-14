# src/functions/graphs/payment.py
"""
Payment graph (deterministic + GHCP SDK hook on submit):
  generate_payment_file -> submit_payment -> terminal
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from src.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from src.functions.graphs.executors.deterministic import generate_payment_file, submit_payment


def build_payment_workflow() -> Workflow:
    n1 = TrackedExecutor(id="gen_file", name="generate_payment_file",
                         executor_type="deterministic", fn=generate_payment_file.execute)
    n2 = TrackedExecutor(id="submit", name="submit_payment",
                         executor_type="deterministic", fn=submit_payment.execute)
    term = TerminalExecutor(id="terminal")
    return WorkflowBuilder(start_executor=n1).add_edge(n1, n2).add_edge(n2, term).build()
