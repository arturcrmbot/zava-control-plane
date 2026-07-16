from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from importlib import import_module

import pytest

from api.shared.domain_contracts import Domain, Phase
from api.shared.function_contracts import Function, PersonaTree
from api.shared.vertical_loader import validate_pack
from api.shared.vertical_pack import (
    DurableFunctionRegistration,
    VerticalUiManifest,
)
from tests.api.shared.vertical_pack_fakes import make_test_pack


def test_domain_contract_is_immutable() -> None:
    contracts = import_module("api.shared.domain_contracts")
    domain = contracts.Domain(
        workflow_type="demo",
        display_name="Demo",
        workflow_id_prefix="DEMO",
        orchestrator_name="DemoOrchestrator",
        operator_surface="demo",
        phases=(contracts.Phase("Intake", "deterministic"),),
        hitl_gates=(),
        skills=(),
    )

    with pytest.raises(FrozenInstanceError):
        domain.function = "ops"


def test_world_registration_declares_named_scales_and_responders() -> None:
    contracts = import_module("api.shared.world_contracts")
    scale = contracts.WorldScaleProfile(
        name="demo",
        build_scenario=lambda _runtime: None,
        default_minutes_per_second=10.0,
    )
    world = contracts.WorldPackRegistration(
        name="demo-world",
        scales={"demo": scale},
        default_scale="demo",
        objective_routes=(),
        responders={},
    )

    assert world.scales["demo"] is scale
    assert world.default_scale == "demo"
    assert world.responders == {}


def _domain() -> Domain:
    return Domain(
        workflow_type="demo",
        display_name="Demo",
        workflow_id_prefix="DEMO",
        orchestrator_name="DemoOrchestrator",
        operator_surface="demo",
        phases=(Phase("Intake", "deterministic"),),
        hitl_gates=(),
        skills=(),
    )


def _function(*owned_domains: str) -> Function:
    return Function(
        name="ops",
        display="Operations",
        operator_surface="ops",
        owns_domains=owned_domains,
        ambient_agents=(),
        kpis=(),
        persona_hierarchy=PersonaTree(role="__legacy__"),
    )


def _pack_with_domain(tmp_path):
    return replace(
        make_test_pack("agency", tmp_path),
        domains={"demo": _domain()},
        organisation_functions={"ops": _function("demo")},
        durable_functions=DurableFunctionRegistration(
            register=lambda _app: None,
            orchestrators=frozenset({"DemoOrchestrator"}),
            activities=frozenset(),
        ),
    )


def test_validation_rejects_domain_key_mismatch(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(pack, domains={"wrong": _domain()})

    with pytest.raises(ValueError, match="domain key 'wrong'"):
        validate_pack(pack)


def test_validation_rejects_function_ownership_mismatch(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(pack, organisation_functions={})

    with pytest.raises(ValueError, match="function ownership mismatch"):
        validate_pack(pack)


def test_validation_rejects_missing_domain_orchestrator(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)
    pack = replace(
        pack,
        durable_functions=DurableFunctionRegistration(
            register=lambda _app: None,
            orchestrators=frozenset(),
            activities=frozenset(),
        ),
    )

    with pytest.raises(ValueError, match="missing orchestrator 'DemoOrchestrator'"):
        validate_pack(pack)


def test_validation_rejects_unknown_runtime_registrations(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)

    with pytest.raises(ValueError, match="unknown ramp workflow 'missing'"):
        validate_pack(replace(pack, ramp_workflow_types=("missing",)))
    with pytest.raises(ValueError, match="unknown projection workflow 'missing'"):
        validate_pack(replace(pack, projections={"missing": lambda _workflow: ()}))
    with pytest.raises(ValueError, match="unknown memory workflow 'missing'"):
        validate_pack(replace(pack, memory_workflow_types=("missing",)))


def test_validation_rejects_unknown_ui_vocabulary(tmp_path) -> None:
    pack = _pack_with_domain(tmp_path)

    with pytest.raises(ValueError, match="unknown UI capabilities"):
        validate_pack(
            replace(
                pack,
                ui=VerticalUiManifest(
                    capabilities=frozenset({"mystery"}),
                    lenses=(),
                    theme={},
                    phase_aliases={},
                ),
            )
        )
    with pytest.raises(ValueError, match="unknown UI lenses"):
        validate_pack(
            replace(
                pack,
                ui=VerticalUiManifest(
                    capabilities=frozenset(),
                    lenses=("mystery",),
                    theme={},
                    phase_aliases={},
                ),
            )
        )
