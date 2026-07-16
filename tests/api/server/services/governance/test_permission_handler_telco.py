from __future__ import annotations

import json
import os
import subprocess
import sys


SCRIPT = r"""
import json
import os

os.environ["AGT_ENFORCE"] = "1"
os.environ["AZURE_STORAGE_CONNECTION_STRING"] = ""

from copilot.session import PermissionRequest
from api.server.services.governance.kernel import kernel
from api.server.services.governance.permission_handler import AGTPermissionHandler

cases = [
    ("proactive-customer-care-entitlement", "customer_care_policy_lookup"),
    ("proactive-customer-care-execution", "customer_care_prepare_notification"),
    ("proactive-customer-care-execution", "customer_care_prepare_credit"),
]
results = {}
for actor, tool in cases:
    request = PermissionRequest(
        kind="mcp",
        server_name="",
        tool_name=tool,
        args={},
    )
    results[tool] = AGTPermissionHandler(
        skill_label=actor,
        workflow_id="WF-TELCO-CARE",
    )(request, {}).kind

print(json.dumps({
    "known_tools": sorted(kernel().known_tools),
    "results": results,
}))
"""


def test_telco_governance_process_loads_only_care_tools() -> None:
    environment = os.environ.copy()
    environment["ZAVA_VERTICAL"] = "telco"
    environment.pop("ZAVA_WORLD", None)
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    evidence = json.loads(result.stdout)

    assert set(evidence["known_tools"]) == {
        "customer_care_policy_lookup",
        "customer_care_prepare_notification",
        "customer_care_prepare_credit",
    }
    assert set(evidence["results"].values()) == {"approved"}
