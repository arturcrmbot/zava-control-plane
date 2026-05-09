"""Projection: vendor-kyc (TASK-017).

Rels emitted: none. Org->TRANSACTS->Org (proposed-by) was dropped in
Phase 1 hardening (TRANSACTS is schema-typed Person→Money). The
proposing-agency linkage is preserved via the workflow's
``source_workflows`` array on both Org nodes.

Payload keys (``data/synthetic/vendor-kyc/vendors.json``)::

    vendor_name, country_of_incorporation, proposing_agency, scenario
"""
from __future__ import annotations

from api.server.services.entity_projections import (
    DecisionWrite,
    EntityWrite,
    RelWrite,
    build_decision,
    slug,
)
from api.shared.types import Workflow

WORKFLOW_TYPE = "vendor-kyc"


def _risk_band(scenario: str) -> str:
    s = scenario.lower()
    if any(tok in s for tok in ("sanctions", "high-risk", "high_risk", "ubo-shell")):
        return "red"
    if any(tok in s for tok in ("amber", "mid", "incomplete")):
        return "amber"
    return "green"


def project(workflow: Workflow) -> list[EntityWrite | RelWrite | DecisionWrite]:
    p = workflow.payload or {}
    vendor_name = str(p.get("vendor_name") or "unknown")
    country = str(p.get("country_of_incorporation") or "")
    agency = str(p.get("proposing_agency") or "unknown")
    scenario = str(p.get("scenario") or "")

    vendor_id = f"ORG-vendor-{slug(vendor_name)}"
    agency_id = f"ORG-agency-{slug(agency)}"
    sw = (workflow.id,)

    ops: list[EntityWrite | RelWrite | DecisionWrite] = [
        EntityWrite(
            kind="Organisation",
            id=vendor_id,
            attrs={
                "name": vendor_name,
                "kind": "vendor",
                "country": country,
                "risk_band": _risk_band(scenario),
            },
            source_workflows=sw,
        ),
        EntityWrite(
            kind="Organisation",
            id=agency_id,
            attrs={"name": agency, "kind": "agency"},
            source_workflows=sw,
        ),
        # NOTE: Org->TRANSACTS->Org dropped in Phase 1 hardening.
    ]

    d = build_decision(
        workflow,
        gate_phase="finance_signoff",
        persona_role="vendor_kyc_finance_bp",
        source_event="workflow.hitl.requested",
        decided_on=(vendor_id,),
        attributes={"vendor_name": vendor_name, "country": country, "scenario": scenario},
    )
    if d is not None:
        ops.append(d)

    return ops
