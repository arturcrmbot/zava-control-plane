from agent_framework import Workflow

from api.functions.graphs._tracked_executor import build_linear_workflow
from api.functions.graphs.executors.agents import (
    agent_proactive_customer_care_entitlement,
)


def build_proactive_customer_care_entitlement_workflow() -> Workflow:
    return build_linear_workflow(
        [
            (
                "entitlement_decision",
                "proactive-customer-care-entitlement",
                "agent",
                agent_proactive_customer_care_entitlement.execute,
            )
        ]
    )
