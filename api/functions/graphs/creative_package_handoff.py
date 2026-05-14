"""Package & Handoff graph (POC3 Phase 6).

  agent_creative_stub -> validate_creative_stub -> terminal

Phase 6 of the creative-campaign orchestrator. The closing phase. v1
stub returns a placeholder `figma_file_url`; real implementation in
Phase 6 of the plan: the `figma` MCP pushes the locked-route stills +
storyboard frames + brief PDF as a new page in the shared demo Figma
file, then the orchestrator stamps the real Figma page URL onto
`workflow.payload.figma_file_url`.
"""
from __future__ import annotations
from agent_framework import Workflow, WorkflowBuilder

from api.functions.graphs._tracked_executor import TrackedExecutor, TerminalExecutor
from api.functions.graphs.executors.agents import agent_creative_stub
from api.functions.graphs.executors.validators import validate_creative_stub


def build_creative_package_handoff_workflow() -> Workflow:
    n1 = TrackedExecutor(
        id="package_handoff",
        name="agent_package_handoff",
        executor_type="agent",
        fn=agent_creative_stub.execute,
    )
    n2 = TrackedExecutor(
        id="val_package_handoff",
        name="validate_package_handoff_schema",
        executor_type="validator",
        fn=validate_creative_stub.execute,
    )
    term = TerminalExecutor(id="terminal")
    return (
        WorkflowBuilder(start_executor=n1)
        .add_edge(n1, n2)
        .add_edge(n2, term)
        .build()
    )
