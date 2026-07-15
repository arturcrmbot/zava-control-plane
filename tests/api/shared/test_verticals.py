from __future__ import annotations

import importlib

import pytest

from api.shared.domains import DOMAINS


MODULE = "api.shared.verticals"


def _verticals_module():
    return importlib.import_module(MODULE)


def test_active_vertical_returns_none_when_env_unset_or_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    verticals = _verticals_module()
    assert verticals.active_vertical() is None

    monkeypatch.setenv("ZAVA_VERTICAL", "   ")
    assert verticals.active_vertical() is None


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
    assert verticals.registered_workflow_types() == ("network-incident",)


def test_registered_workflow_types_preserves_default_registry_when_vertical_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verticals = _verticals_module()
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)

    assert verticals.registered_workflow_types() == tuple(DOMAINS.keys())


def test_active_vertical_rejects_unknown_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    verticals = _verticals_module()
    monkeypatch.setenv("ZAVA_VERTICAL", "mystery")

    with pytest.raises(ValueError, match="Unknown ZAVA_VERTICAL"):
        verticals.active_vertical()
