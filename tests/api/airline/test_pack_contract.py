from pathlib import Path

from api.shared.vertical_loader import build_runtime
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

    assert workflow_type in AIRLINE_DOMAINS
    assert "aog-engineering-recovery" in AIRLINE_DOMAINS
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
        "aog-recovery-ranker",
        "schedule-resilience-ranker",
    }
    assert set(AIRLINE_PERSONAS) == {"duty_operations_manager", "engineering_duty_manager", "network_operations_director"}
    assert set(AIRLINE_AUTHORITY) == {"duty_operations_manager", "engineering_duty_manager", "network_operations_director"}


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


def test_manifest_recordings_curated_dirs_exist_and_are_directories(tmp_path: Path) -> None:
    """Every manifest curated_dir must exist and be a directory."""
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "airline"},
        data_root=tmp_path,
    )
    pack = runtime.pack

    if pack.recordings and pack.recordings.curated_dirs:
        for curated_dir in pack.recordings.curated_dirs:
            assert curated_dir.exists(), (
                f"Manifest recordings curated_dir {curated_dir} does not exist"
            )
            assert curated_dir.is_dir(), (
                f"Manifest recordings curated_dir {curated_dir} is not a directory"
            )


def test_seller_review_remains_human_owned_and_pending() -> None:
    review = (Path(__file__).parents[3] / "verticals/airline/SELLER-REVIEW.md").read_text(
        encoding="utf-8"
    )
    assert "**Status:** PENDING" in review
    assert "| Build ready | PASS |" in review
    assert "| Demo ready | PENDING |" in review
