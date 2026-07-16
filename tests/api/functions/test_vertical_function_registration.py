from __future__ import annotations

import json
import os
import subprocess
import sys


INDEX_SCRIPT = r"""
import json
import function_app
functions = function_app.app.get_functions()
print(json.dumps(sorted(function.get_function_name() for function in functions)))
"""

TELCO_FUNCTIONS = {
    "NetworkIncidentOrchestrator",
    "ProactiveCustomerCareOrchestrator",
    "OrderToActivateOrchestrator",
    "network_incident_impact_activity_trigger",
    "network_incident_reroute_activity_trigger",
    "customer_care_impact_activity_trigger",
    "customer_care_entitlement_activity_trigger",
    "customer_care_execution_activity_trigger",
    "order_activation_feasibility_activity_trigger",
    "order_activation_prepare_activity_trigger",
}
AGENCY_SENTINELS = {
    "ExpenseClaimOrchestrator",
    "HiringOrchestrator",
    "FleetTravelPreapprovalOrchestrator",
    "SurgeStaffingOrchestrator",
    "intake_activity_trigger",
}


def _indexed_functions(vertical: str, tmp_path) -> set[str]:
    environment = os.environ.copy()
    environment.update(
        {
            "AZURE_STORAGE_CONNECTION_STRING": "",
            "ENTITY_PLANE_ENABLED": "0",
            "PORTAL_DATA_DIR": str(tmp_path),
            "ZAVA_VERTICAL": vertical,
        }
    )
    environment.pop("ZAVA_WORLD", None)
    result = subprocess.run(
        [sys.executable, "-c", INDEX_SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    return set(json.loads(result.stdout.splitlines()[-1]))


def test_agency_functions_index_excludes_telco(tmp_path) -> None:
    indexed = _indexed_functions("agency", tmp_path)

    assert AGENCY_SENTINELS <= indexed
    assert TELCO_FUNCTIONS.isdisjoint(indexed)


def test_telco_functions_index_excludes_agency(tmp_path) -> None:
    indexed = _indexed_functions("telco", tmp_path)

    assert TELCO_FUNCTIONS <= indexed
    assert AGENCY_SENTINELS.isdisjoint(indexed)
