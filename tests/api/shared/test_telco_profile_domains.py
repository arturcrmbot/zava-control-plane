from __future__ import annotations

from api.shared.vertical_loader import build_runtime
from verticals.telco.process_profiles import STANDARD_PROCESS_PROFILES


EXPECTED_FUNCTIONS = {
    "network-operations",
    "service-operations",
    "customer-success",
    "commercial-risk",
}
EXPECTED_STANDARD_ORCHESTRATORS = {
    "TelcoDetectDiagnoseActOrchestrator",
    "TelcoForecastSimulatePlanOrchestrator",
    "TelcoCaseTriageResolveOrchestrator",
    "TelcoOrderFulfilVerifyOrchestrator",
    "TelcoRiskInvestigateGovernOrchestrator",
    "TelcoAssistRecommendActOrchestrator",
}


def test_telco_pack_exposes_37_executable_processes(tmp_path):
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)

    assert len(runtime.pack.domains) == 37
    assert all(not domain.stub for domain in runtime.pack.domains.values())
    assert set(STANDARD_PROCESS_PROFILES) <= set(runtime.pack.domains)
    assert {
        runtime.pack.domains[name].orchestrator_name
        for name in STANDARD_PROCESS_PROFILES
    } == EXPECTED_STANDARD_ORCHESTRATORS


def test_standard_profiles_have_exactly_one_function_owner(tmp_path):
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)
    functions = runtime.pack.organisation_functions

    assert set(functions) == EXPECTED_FUNCTIONS
    owners = {
        workflow_type: function.name
        for function in functions.values()
        for workflow_type in function.owns_domains
    }
    assert len(owners) == 37
    for workflow_type, profile in STANDARD_PROCESS_PROFILES.items():
        assert owners[workflow_type] == profile.function


def test_standard_hitl_personae_are_registered_with_authority(tmp_path):
    runtime = build_runtime({"ZAVA_VERTICAL": "telco"}, data_root=tmp_path)

    for role in {
        "network_ops_director",
        "service_ops_manager",
        "cs_manager",
        "commercial_risk_director",
    }:
        assert role in runtime.pack.personas
        assert role in runtime.pack.authority
