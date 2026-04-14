# src/functions/graphs/intake.py
"""
Intake graph (hybrid):
  doc_intelligence_extract -> agent_field_extractor -> agent_line_item_extractor
    -> validate_required_fields -> agent_anomaly_flagger -> validate_amount_consistency
    -> terminal
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from src.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from src.functions.graphs.executors.deterministic import doc_intelligence_extract
from src.functions.graphs.executors.agents import (
    agent_field_extractor, agent_line_item_extractor, agent_anomaly_flagger,
)
from src.functions.graphs.executors.validators import (
    validate_required_fields, validate_amount_consistency,
)


def build_intake_workflow() -> Workflow:
    n1 = TrackedExecutor(id="doc_intel", name="doc_intelligence_extract",
                         executor_type="deterministic", fn=doc_intelligence_extract.execute)
    n2 = TrackedExecutor(id="field_ext", name="agent_field_extractor",
                         executor_type="agent", fn=agent_field_extractor.execute)
    n3 = TrackedExecutor(id="line_ext", name="agent_line_item_extractor",
                         executor_type="agent", fn=agent_line_item_extractor.execute)
    n4 = TrackedExecutor(id="val_req", name="validate_required_fields",
                         executor_type="validator", fn=validate_required_fields.execute)
    n5 = TrackedExecutor(id="anomaly", name="agent_anomaly_flagger",
                         executor_type="agent", fn=agent_anomaly_flagger.execute)
    n6 = TrackedExecutor(id="val_amt", name="validate_amount_consistency",
                         executor_type="validator", fn=validate_amount_consistency.execute)
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, n3)
        .add_edge(n3, n4)
        .add_edge(n4, n5)
        .add_edge(n5, n6)
        .add_edge(n6, term)
        .build()
    )
