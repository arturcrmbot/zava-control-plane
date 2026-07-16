from __future__ import annotations

import importlib

import pytest

from api.shared.domains import DOMAINS


MODULE = "api.shared.verticals"
TELCO_WORKFLOW_TYPES = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}


@pytest.fixture(autouse=True)
def _clear_active_runtime():
    from api.shared.vertical_loader import active_runtime

    active_runtime.cache_clear()
    yield
    active_runtime.cache_clear()


def _verticals_module():
    return importlib.import_module(MODULE)


def test_active_vertical_defaults_to_agency_when_env_unset_or_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    verticals = _verticals_module()
    profile = verticals.active_vertical()
    assert profile is not None
    assert profile.name == "agency"
    assert profile.world is None

    monkeypatch.setenv("ZAVA_VERTICAL", "   ")
    blank_profile = verticals.active_vertical()
    assert blank_profile is not None
    assert blank_profile.name == "agency"
    assert blank_profile.world is None


def test_active_vertical_selects_telco_profile_and_intersects_registered_domains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verticals = _verticals_module()
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")

    assert verticals.active_vertical() == verticals.VerticalProfile(
        name="telco",
        world="telco",
        workflow_types=(
            "network-incident",
            "proactive-customer-care",
            "order-to-activate",
        ),
        ramp_workflow_types=(),
    )
    assert verticals.registered_workflow_types() == (
        "network-incident",
        "proactive-customer-care",
        "order-to-activate",
    )


def test_registered_workflow_types_defaults_to_agency_registry_when_vertical_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verticals = _verticals_module()
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)

    assert verticals.registered_workflow_types() == tuple(
        workflow_type
        for workflow_type in DOMAINS
        if workflow_type not in TELCO_WORKFLOW_TYPES
    )


def test_active_vertical_rejects_unknown_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    verticals = _verticals_module()
    monkeypatch.setenv("ZAVA_VERTICAL", "mystery")

    with pytest.raises(ValueError, match="unknown vertical 'mystery'"):
        verticals.active_vertical()
