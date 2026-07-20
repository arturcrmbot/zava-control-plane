from __future__ import annotations

from api.server.services.blueprint_inventory import _build_domain_manifest
from api.shared.domains import DOMAINS as AGENCY_DOMAINS
from api.shared.vertical_loader import build_runtime
from verticals.telco.domains import TELCO_DOMAINS


TELCO_WORKFLOW_TYPES = set(TELCO_DOMAINS)


def _live_workflow_types(manifest) -> set[str]:
    return {
        entry["workflow_type"]
        for entry in manifest
        if entry["status"] == "live" and entry["workflow_type"]
    }


def test_build_domain_manifest_defaults_to_agency_domains(tmp_path) -> None:
    runtime = build_runtime({}, data_root=tmp_path)

    manifest = _build_domain_manifest(runtime)

    assert _live_workflow_types(manifest) == set(AGENCY_DOMAINS) | {
        "onboarding"
    }
    assert TELCO_WORKFLOW_TYPES.isdisjoint(
        _live_workflow_types(manifest)
    )


def test_build_domain_manifest_filters_to_telco_domains(tmp_path) -> None:
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )

    manifest = _build_domain_manifest(runtime)

    assert _live_workflow_types(manifest) == TELCO_WORKFLOW_TYPES
    assert not any(
        entry["workflow_type"] == "onboarding"
        for entry in manifest
    )
