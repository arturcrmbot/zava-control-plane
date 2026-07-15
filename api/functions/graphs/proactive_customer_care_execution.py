from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import (
    agent_proactive_customer_care_execution,
)


def build_proactive_customer_care_execution_workflow() -> Workflow:
    return build_linear_workflow(
        [
            (
                "care_execution",
                "proactive-customer-care-execution",
                "agent",
                agent_proactive_customer_care_execution.execute,
            )
        ]
    )
