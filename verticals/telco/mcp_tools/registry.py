from __future__ import annotations

from .commercial import (
    commercial_evaluate_entitlement_tool,
    commercial_prepare_action_tool,
    commercial_query_customer_tool,
    commercial_query_order_revenue_tool,
)
from .network import (
    network_prepare_action_tool,
    network_query_impact_tool,
    network_query_state_tool,
    network_validate_action_tool,
)
from .operations import (
    operations_match_resources_tool,
    operations_prepare_case_action_tool,
    operations_query_case_tool,
    operations_search_runbook_tool,
)
from .twin import (
    twin_compare_scenarios_tool,
    twin_forecast_tool,
    twin_publish_plan_tool,
    twin_query_external_signal_tool,
)


TOOL_BY_NAME = {
    "network_query_state": network_query_state_tool,
    "network_query_impact": network_query_impact_tool,
    "network_validate_action": network_validate_action_tool,
    "network_prepare_action": network_prepare_action_tool,
    "operations_query_case": operations_query_case_tool,
    "operations_search_runbook": operations_search_runbook_tool,
    "operations_match_resources": operations_match_resources_tool,
    "operations_prepare_case_action": operations_prepare_case_action_tool,
    "commercial_query_customer": commercial_query_customer_tool,
    "commercial_query_order_revenue": commercial_query_order_revenue_tool,
    "commercial_evaluate_entitlement": commercial_evaluate_entitlement_tool,
    "commercial_prepare_action": commercial_prepare_action_tool,
    "twin_forecast": twin_forecast_tool,
    "twin_compare_scenarios": twin_compare_scenarios_tool,
    "twin_query_external_signal": twin_query_external_signal_tool,
    "twin_publish_plan": twin_publish_plan_tool,
}
