from verticals.airline.agents import AIRLINE_AGENTS
from verticals.airline.authority import AIRLINE_AUTHORITY
from verticals.airline.domains import AIRLINE_DOMAINS
from verticals.airline.functions import AIRLINE_FUNCTIONS
from verticals.airline.personas import AIRLINE_PERSONAS
from verticals.airline.process_profiles import AIRLINE_PROCESS_PROFILES


def test_airline_declares_only_the_golden_hero() -> None:
    workflow_type = "integrated-hub-disruption-recovery"
    domain = AIRLINE_DOMAINS[workflow_type]
    profile = AIRLINE_PROCESS_PROFILES[workflow_type]

    assert tuple(AIRLINE_DOMAINS) == (workflow_type,)
    assert domain.stub is False
    assert domain.orchestrator_name == "AirlineIntegratedHubRecoveryOrchestrator"
    assert tuple(phase.kind for phase in domain.phases) == (
        "deterministic",
        "agent",
        "agent",
        "hitl",
        "deterministic",
        "deterministic",
    )
    assert profile.sensor_id == "sensor:integrated_hub_disruption"
    assert profile.command_type == "airline.commit_recovery_plan"
    assert AIRLINE_FUNCTIONS["operations-control"].owns_domains == (workflow_type,)
    assert set(AIRLINE_AGENTS) == {
        "network-impact-assessor",
        "recovery-option-ranker",
    }
    assert set(AIRLINE_PERSONAS) == {"duty_operations_manager"}
    assert set(AIRLINE_AUTHORITY) == {"duty_operations_manager"}


def test_airline_contract_modules_have_no_travel_business_imports() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    pack = root / "verticals" / "airline"
    leaked = []
    for path in pack.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "verticals.travel" in source:
            leaked.append(str(path.relative_to(root)))
    assert leaked == []
