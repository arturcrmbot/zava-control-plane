from __future__ import annotations

from api.server.services.entity_projections import PROJECTIONS
from api.shared.domains import DOMAINS
from api.shared.vertical_loader import build_runtime


TELCO_WORKFLOWS = {
    "network-incident",
    "proactive-customer-care",
    "order-to-activate",
}


def test_agency_projection_registry_matches_agency_domains():
    assert set(PROJECTIONS) == set(DOMAINS)
    assert TELCO_WORKFLOWS.isdisjoint(PROJECTIONS)


def test_telco_projection_registry_is_exact(tmp_path):
    runtime = build_runtime(
        {"ZAVA_VERTICAL": "telco"},
        data_root=tmp_path,
    )
    assert set(runtime.pack.projections) == TELCO_WORKFLOWS


def test_every_agency_projection_is_callable():
    for workflow_type, projection in PROJECTIONS.items():
        assert callable(projection), (
            f"projection for {workflow_type!r} is not callable"
        )
