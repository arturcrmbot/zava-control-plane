from __future__ import annotations

import json
import os
import subprocess
import sys


EXPECTED_ORCHESTRATORS = {
    "OutageRiskManagementOrchestrator",
    "PredictiveSiteMaintenanceOrchestrator",
    "FieldRepairDispatchOrchestrator",
    "CapacityOptimizationOrchestrator",
    "ServiceTicketResolutionOrchestrator",
    "RetentionOrchestrationOrchestrator",
}


def test_telco_functions_indexes_cascade_orchestrators(tmp_path):
    environment = os.environ.copy()
    environment.update(
        {
            "ENTITY_PLANE_ENABLED": "0",
            "PORTAL_DATA_DIR": str(tmp_path),
            "ZAVA_VERTICAL": "telco",
        }
    )
    environment.pop("ZAVA_WORLD", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, function_app;"
                "print(json.dumps(sorted("
                "f.get_function_name() for f in function_app.app.get_functions()"
                ")))"
            ),
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    indexed = set(json.loads(result.stdout.splitlines()[-1]))
    assert EXPECTED_ORCHESTRATORS <= indexed
    assert "telco_cascade_decision_activity_trigger" in indexed
