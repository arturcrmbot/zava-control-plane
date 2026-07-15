from __future__ import annotations

import importlib

import pytest

from api.shared.domains import DOMAINS as REGISTRY_DOMAINS


@pytest.fixture(autouse=True)
def _restore_blueprint_inventory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    yield
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)
    from api.server.services import blueprint_inventory

    importlib.reload(blueprint_inventory)


def _reload_blueprint_inventory():
    from api.server.services import blueprint_inventory

    return importlib.reload(blueprint_inventory)


def _registry_manifest_types(module) -> set[str]:
    return {
        entry["workflow_type"]
        for entry in module.DOMAINS
        if entry["status"] == "live" and entry["workflow_type"] in REGISTRY_DOMAINS
    }


def test_build_domain_manifest_keeps_registered_domains_when_vertical_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZAVA_VERTICAL", raising=False)

    module = _reload_blueprint_inventory()

    assert _registry_manifest_types(module) == set(REGISTRY_DOMAINS.keys())


def test_build_domain_manifest_filters_to_telco_domains(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZAVA_VERTICAL", "telco")

    module = _reload_blueprint_inventory()

    assert _registry_manifest_types(module) == {"network-incident"}
    assert any(entry["workflow_type"] == "onboarding" for entry in module.DOMAINS)
