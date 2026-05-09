"""Phase 1 sub-phase 7 — TASK-040.

Executable proxy for the live TASK-039 profile-autonomous run. Constructs
``AppState`` in-process, manually upserts a workflow, emits the matching
``workflow.completed`` event on the bus, and asserts that the entity-graph
plane received the projected entity nodes.

Per the documented sub-phase 3 caveats (resolved in Phase 1 hardening),
projections used to emit non-schema attrs and schema-invalid rels — both
of which were exception-isolated by the reflector's per-op try/except.
After hardening, the projections are schema-aligned (non-column attrs
land in the ``attributes`` JSON blob; impossible rels are dropped) and
the smoke now lands the Asset + Decision for creative-campaign too.

Judgment call (documented for reviewers)
----------------------------------------
The TASK-040 plan text says ``touched_by(workflow_id)`` should return
``≥3 entities (vendor org, agency org, decision)``. The actual
:meth:`EntityGraph.touched_by` docstring explicitly excludes Decisions —
they live on a scalar ``workflow_id`` column, not on a ``source_workflows``
array. So the assertions here split the contract:

* ``touched_by`` is asserted ``≥2`` (the two Org nodes — verified to land);
* the Decision is asserted separately via
  ``by_type("Decision", workflow_id=<wf_id>) ≥ 1``, which is the API the
  EntityGraph docstring directs callers to use.

This is the executable contract the entity plane actually offers today.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import time
from pathlib import Path


def _reload_state_module(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    import api.server.state as state_mod
    importlib.reload(state_mod)
    return state_mod


def _wait_for_bus(state) -> None:
    """The bus dispatches synchronously today, but we keep this helper as a
    seam in case future changes make dispatch async."""
    # No-op for now; reflector callbacks run inside ``bus.emit``.
    return None


def test_vendor_kyc_smoke_projects_entities_and_decision(tmp_path: Path, monkeypatch):
    state_mod = _reload_state_module(monkeypatch, tmp_path)
    from api.shared.events import FleetEvent
    from api.shared.types import Workflow

    asyncio.run(state_mod.app_state.aclose())

    # Load fixture entry [0] — Acme Holdings / VMLY&R.
    vendors = json.loads(
        (Path("data/synthetic/vendor-kyc/vendors.json")).read_text()
    )
    fixture = vendors[0]

    state = state_mod.AppState()
    try:
        wf_id = "WF-VKY-SMOKE-1"
        now = time.time()
        wf = Workflow(
            id=wf_id,
            type="vendor-kyc",
            payload={
                "vendor_name": fixture["vendor_name"],
                "country_of_incorporation": fixture["country_of_incorporation"],
                "proposing_agency": fixture["proposing_agency"],
                "scenario": fixture["scenario"],
                # Convention from sub-phase 3: projection looks up
                # payload["decisions"] by gate_phase. vendor_kyc.py uses
                # "finance_signoff" / persona "vendor_kyc_finance_bp".
                "decisions": [
                    {
                        "phase": "finance_signoff",
                        "verdict": "approved",
                        "reason": "smoke-test",
                        "decided_at": "2026-05-09T10:00:00",
                        "persona_role": "vendor_kyc_finance_bp",
                    }
                ],
            },
            current_phase="Intake",
            created_at=now,
            sla_due_at=now + 3600,
            jurisdiction="London-Zava",
            agency=fixture["proposing_agency"],
        )
        state.store.upsert_workflow(wf)
        state.bus.emit(FleetEvent(type="workflow.completed", workflow_id=wf_id))
        _wait_for_bus(state)

        touched = state.entities.touched_by(wf_id)
        # vendor Org + agency Org. Decision is excluded by touched_by by
        # design (see EntityGraph.touched_by docstring) and is asserted
        # separately below.
        assert len(touched) >= 2, f"expected ≥2 entities touched by {wf_id}, got {len(touched)}: {touched}"

        decisions = state.entities.by_type("Decision", workflow_id=wf_id)
        assert len(decisions) >= 1, f"expected ≥1 Decision for {wf_id}, got {len(decisions)}"
    finally:
        asyncio.run(state.aclose())


def test_creative_campaign_smoke_projects_entities_and_decision(tmp_path: Path, monkeypatch):
    state_mod = _reload_state_module(monkeypatch, tmp_path)
    from api.shared.events import FleetEvent
    from api.shared.types import Workflow

    asyncio.run(state_mod.app_state.aclose())

    briefs = json.loads(
        (Path("data/synthetic/creative-campaign/briefs.json")).read_text()
    )
    fixture = briefs[0]

    state = state_mod.AppState()
    try:
        wf_id = "WF-CC-SMOKE-1"
        now = time.time()
        wf = Workflow(
            id=wf_id,
            type="creative-campaign",
            payload={
                **{k: v for k, v in fixture.items() if k != "id"},
                # creative_campaign.py iterates 5 gate phases; injecting one
                # decision (brief_capture) is enough to land a Decision node.
                "decisions": [
                    {
                        "phase": "brief_capture",
                        "verdict": "approved",
                        "reason": "smoke-test",
                        "decided_at": "2026-05-09T10:00:00",
                        "persona_role": "creative_director",
                    }
                ],
            },
            current_phase="Intake",
            created_at=now,
            sla_due_at=now + 3600,
            jurisdiction="London-Zava",
            agency=fixture.get("agency", "unknown"),
        )
        state.store.upsert_workflow(wf)
        state.bus.emit(FleetEvent(type="workflow.completed", workflow_id=wf_id))
        _wait_for_bus(state)

        touched = state.entities.touched_by(wf_id)
        # customer Org + agency Org + the campaign Asset (now lands cleanly
        # after the Phase 1 hardening fix: the Asset's non-schema attrs
        # were rerouted into the ``attributes`` JSON blob, and the Asset
        # op no longer aborts the loop).
        assert len(touched) >= 2, f"expected ≥2 entities touched by {wf_id}, got {len(touched)}: {touched}"

        # Phase 1 hardening: the Decision op used to be skipped because
        # the Asset op (earlier in the loop) raised a Binder exception
        # that aborted every subsequent op via the reflector's outer
        # try/except. With per-op isolation + schema-aligned attrs, the
        # Decision now lands.
        decisions = state.entities.by_type("Decision", workflow_id=wf_id)
        assert len(decisions) >= 1, (
            f"expected ≥1 Decision for {wf_id} after Phase 1 hardening, got {len(decisions)}"
        )
    finally:
        asyncio.run(state.aclose())
