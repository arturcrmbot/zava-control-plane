"""POC3 creative-campaign — TASK-009 verification.

Phase 1 ships:
  - Domain registry entry (creative-campaign + 5 HITL gates + creative_director persona)
  - Orchestrator (10-phase generator) + 5 graphs (stubs against canned fixtures)
  - Spawner + simulator route + corpus loader for briefs.json
  - 12 demo briefs + 54 cached SVG fixtures (3 briefs × 12 stills + 6 storyboard frames)

This file proves the substrate sees creative-campaign as a first-class
domain — without booting Azurite + Functions — by verifying:

  1. The registry entry resolves correctly through every helper.
  2. build_creative_campaign_workflow accepts both inline + corpus records.
  3. _pick_record can walk the briefs.json corpus.
  4. The persona's decision_policy compiles + decides correctly for each
     of the five HITL gates.
  5. The orchestrator generator yields the expected sequence (registry
     of activity calls + suspends) with a fake DurableOrchestrationContext.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from api.shared import domains as _registry
from api.server.services import persona_responder
from api.server.services.simulator_orchestrator import _pick_record, _load_corpus
from api.server.services.synthetic_data import build_creative_campaign_workflow


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


def test_creative_campaign_registered_with_5_gates():
    cmp = _registry.DOMAINS["creative-campaign"]
    assert cmp.workflow_id_prefix == "CMP"
    assert cmp.orchestrator_name == "CreativeCampaignOrchestrator"
    assert cmp.operator_surface == "producer-queue"
    assert len(cmp.phases) == 10
    assert len(cmp.hitl_gates) == 5
    gate_names = {g.gate_phase for g in cmp.hitl_gates}
    assert gate_names == {
        "brief_capture", "brief_approval", "concept_lock",
        "storyboard_approval", "final_signoff",
    }
    # All five gates use the same creative_director persona — this is the
    # whole point of the multi-gate-one-persona design.
    assert {g.persona for g in cmp.hitl_gates} == {"creative_director"}


def test_creative_campaign_personae_referenced_from_registry():
    assert "creative_director" in _registry.all_personae()


def test_creative_campaign_prefix_resolves_workflow_type():
    domain = _registry.by_prefix("CMP-0042")
    assert domain is not None
    assert domain.workflow_type == "creative-campaign"


@pytest.mark.parametrize("phase,expected_event", [
    ("brief_capture", "voice_complete"),
    ("brief_approval", "brief_approval_decision"),
    ("concept_lock", "concept_lock_decision"),
    ("storyboard_approval", "storyboard_approval_decision"),
    ("final_signoff", "final_signoff_decision"),
])
def test_resolve_external_event_for_each_gate(phase, expected_event):
    assert _registry.resolve_external_event("creative-campaign", phase) == expected_event


def test_wake_hints_include_creative_signals():
    hints = _registry.all_wake_hints()
    assert "creative.content_safety.rejected" in hints
    assert "creative.brand.distinctiveness_low" in hints


# --------------------------------------------------------------------------
# synthetic_data builder
# --------------------------------------------------------------------------


def test_build_workflow_inline_record():
    """build_creative_campaign_workflow with no record synthesises a
    minimal brief with all required fields for the persona's brief_approval
    decision policy (audience + mandatory_messages + kpis)."""
    w = build_creative_campaign_workflow("CMP-9999")
    assert w.id == "CMP-9999"
    assert w.type == "creative-campaign"
    assert w.current_phase == "brief_capture"
    brief = (w.payload or {}).get("brief") or {}
    assert brief.get("audience")
    assert brief.get("mandatory_messages")
    assert brief.get("kpis")


def test_build_workflow_from_corpus_record():
    """When a record is passed, semantic fields override the synthesised
    defaults. The agency + jurisdiction lift onto the Workflow record."""
    record = {
        "id": "BRF-TEST",
        "client_brand": "Voltari",
        "category": "ev_reveal",
        "audience": "test audience",
        "mandatory_messages": ["m1", "m2"],
        "channels": ["test"],
        "kpis": {"awareness": "+10%"},
        "jurisdictions": ["DE"],
        "agency": "Wunderman Thompson",
        "scenario": "clean",
    }
    w = build_creative_campaign_workflow("CMP-T1", record=record)
    assert (w.payload or {}).get("brief", {}).get("client_brand") == "Voltari"
    assert (w.payload or {}).get("scenario") == "clean"
    assert w.agency == "Wunderman Thompson"
    assert w.jurisdiction == "DE-Zava"


# --------------------------------------------------------------------------
# Corpus loader
# --------------------------------------------------------------------------


def test_corpus_briefs_json_seeded_and_loadable():
    """The demo briefs.json file ships with 12 records covering 5 brands
    and at least one 'escalated' scenario for the Stage-7 demo beat."""
    records = _load_corpus("creative-campaign")
    assert len(records) >= 12
    brands = {r.get("client_brand") for r in records}
    assert brands == {"Solene", "Voltari", "Verdaire", "Heritor"}
    scenarios = {r.get("scenario") for r in records}
    assert "clean" in scenarios
    assert "escalated" in scenarios


def test_pick_record_roundrobin_walks_corpus():
    """Successive _pick_record calls walk the corpus deterministically."""
    # Reset cursor for test isolation
    from api.server.services.simulator_orchestrator import reset_seed_corpus_cache
    reset_seed_corpus_cache()
    seen_ids = []
    for _ in range(5):
        r = _pick_record("creative-campaign")
        assert r is not None
        seen_ids.append(r["id"])
    # No duplicates in the first 5 picks (corpus has 12 records)
    assert len(set(seen_ids)) == 5


def test_pick_record_filtered_by_scenario():
    """The escalated brief (BRF-012) is the only one matching scenario=escalated."""
    from api.server.services.simulator_orchestrator import reset_seed_corpus_cache
    reset_seed_corpus_cache()
    r = _pick_record("creative-campaign", scenario="escalated")
    assert r is not None
    assert r["scenario"] == "escalated"
    assert r["id"] == "BRF-012"


# --------------------------------------------------------------------------
# Persona decision policy — one assertion per gate
# --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_personae(monkeypatch):
    """Force fresh load of the creative_director persona for every test."""
    monkeypatch.setenv("PERSONA_AUTO_CLOSE", "creative_director")
    persona_responder.PERSONA_DEFINITIONS = persona_responder._load_personae()


def _decide(phase: str, context: dict) -> dict:
    """Apply the creative_director persona's decision_policy to a parked
    context for `phase`. Returns the responder's resolving event payload."""
    persona = persona_responder.PERSONA_DEFINITIONS["creative_director"]
    ctx = {**context, "phase": phase}
    return persona.decide(ctx)


def test_persona_brief_capture_synthesises_transcript():
    out = _decide("brief_capture", {
        "brief": {
            "client_brand": "Solene",
            "category": "luxury_fragrance",
            "audience": "European 25-44",
            "mandatory_messages": ["regenerative provenance"],
        },
    })
    assert out["decision"] == "approve"
    assert "transcript" in out
    assert "Solene" in out["transcript"]
    assert out.get("voice_score", 0) > 0


def test_persona_brief_approval_approves_complete_brief():
    out = _decide("brief_approval", {
        "brief_synthesis": {
            "brief_json": {
                "audience": "test",
                "mandatory_messages": ["m1"],
                "kpis": {"awareness": "+10%"},
            },
        },
    })
    assert out["decision"] == "approve"


def test_persona_brief_approval_rejects_incomplete_brief():
    out = _decide("brief_approval", {
        "brief_synthesis": {"brief_json": {"audience": "test"}},
    })
    assert out["decision"] == "reject"
    assert "mandatory_messages" in out["reason"]
    assert "kpis" in out["reason"]


def test_persona_concept_lock_picks_best_route():
    out = _decide("concept_lock", {
        "concept_fanout": {
            "routes": [
                {"route_name": "route-A", "brand_fit": 0.7, "distinctiveness": 0.5},
                {"route_name": "route-B", "brand_fit": 0.9, "distinctiveness": 0.8},
                {"route_name": "route-C", "brand_fit": 0.6, "distinctiveness": 0.7},
            ],
        },
    })
    assert out["decision"] == "approve"
    assert out["locked_route"] == "route-B"


def test_persona_concept_lock_escalates_low_brand_fit():
    out = _decide("concept_lock", {
        "concept_fanout": {
            "routes": [
                {"route_name": "route-A", "brand_fit": 0.4, "distinctiveness": 0.3},
                {"route_name": "route-B", "brand_fit": 0.5, "distinctiveness": 0.4},
            ],
        },
    })
    assert out["decision"] == "escalate"


def test_persona_storyboard_approval_requires_six_frames():
    out_ok = _decide("storyboard_approval", {
        "storyboard_render": {
            "frames": ["1", "2", "3", "4", "5", "6"],
        },
    })
    assert out_ok["decision"] == "approve"

    out_short = _decide("storyboard_approval", {
        "storyboard_render": {"frames": ["1", "2", "3"]},
    })
    assert out_short["decision"] == "reject"


def test_persona_final_signoff_escalates_on_content_safety_flag():
    out_clean = _decide("final_signoff", {
        "concept_fanout": {"content_safety_flag": False},
        "storyboard_render": {"content_safety_flag": False},
    })
    assert out_clean["decision"] == "approve"

    out_unsafe = _decide("final_signoff", {
        "concept_fanout": {"content_safety_flag": False},
        "storyboard_render": {"content_safety_flag": True},
    })
    assert out_unsafe["decision"] == "escalate"


# --------------------------------------------------------------------------
# Cached image fixtures
# --------------------------------------------------------------------------


def test_cached_image_fixtures_present_for_three_demo_briefs():
    """Each of BRF-001 / BRF-003 / BRF-004 ships with 12 concept stills
    (3 routes × 4) + 6 storyboard frames = 18 SVG fixtures."""
    root = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "creative-campaign" / "cached"
    for brief_id in ("BRF-001", "BRF-003", "BRF-004"):
        for route in ("route-A", "route-B", "route-C"):
            for n in range(1, 5):
                p = root / brief_id / route / f"{n}.svg"
                assert p.exists(), f"missing fixture {p}"
        for n in range(1, 7):
            p = root / brief_id / "storyboard" / f"{n}.svg"
            assert p.exists(), f"missing storyboard fixture {p}"


# --------------------------------------------------------------------------
# Orchestrator generator — verify yield sequence with fake DF context
# --------------------------------------------------------------------------


class _FakeTask:
    def __init__(self, result=None):
        self.result = result
    def cancel(self):
        pass


class _FakeContext:
    """Minimal stand-in for DurableOrchestrationContext just enough to
    walk the orchestrator generator and assert its yield sequence."""
    def __init__(self, *, brief, decisions: list[dict]):
        self.instance_id = "FAKE-INST"
        self._input = {
            "workflow_id": "CMP-FAKE",
            "type": "creative-campaign",
            "brief": brief,
            "brief_id": brief.get("id"),
        }
        self._decisions = list(decisions)
        self._calls: list[tuple[str, dict]] = []

    @property
    def current_utc_datetime(self):
        import datetime
        return datetime.datetime(2026, 5, 5, tzinfo=datetime.timezone.utc)

    def get_input(self):
        return self._input

    def call_activity(self, name: str, payload: dict):
        self._calls.append((name, payload))
        # Return a dict-shaped result; test harness asserts based on calls
        return {"phase": payload.get("phase", name), "stub": True}

    def wait_for_external_event(self, name: str):
        # Pop the next decision off the queue and tag it with the event name.
        if self._decisions:
            decision = self._decisions.pop(0)
        else:
            decision = {"decision": "approve"}
        return _FakeTask(result=decision)

    def create_timer(self, _when):
        return _FakeTask()

    def task_any(self, tasks):
        # Always pick the first task (the event), never the timer.
        return tasks[0]


def test_orchestrator_walks_all_10_phases_with_5_approvals():
    """When all 5 HITL gates approve, the orchestrator generator runs
    every activity and returns status=completed."""
    from api.functions.workflows.creative_campaign import creative_campaign_orchestration

    brief = {"id": "BRF-001", "client_brand": "Solene"}
    # 5 approvals — one per gate. brief_capture also returns approve+transcript.
    decisions = [
        {"decision": "approve", "transcript": "stub", "voice_score": 0.9},
        {"decision": "approve"},
        {"decision": "approve"},
        {"decision": "approve"},
        {"decision": "approve"},
    ]
    ctx = _FakeContext(brief=brief, decisions=decisions)

    gen = creative_campaign_orchestration(ctx)
    # Drive the generator to completion. Each yield is a future whose
    # .result we feed back via .send(). Use the wait_for_external_event
    # results as-is and the call_activity results from the fake context.
    result = None
    sent = None
    while True:
        try:
            yielded = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            result = stop.value
            break
        # Generator yields either a "task" (from create_timer / wait_for_external_event)
        # or the dict returned by call_activity (which our fake returns directly).
        if isinstance(yielded, _FakeTask):
            sent = yielded.result
        elif isinstance(yielded, dict):
            sent = yielded
        else:
            sent = yielded

    assert result is not None
    assert result["status"] == "completed"
    # All 5 agentic activities ran
    activity_names = [n for n, _ in ctx._calls if not n.startswith("checkpoint")]
    assert "creative_brief_synthesis_activity_trigger" in activity_names
    assert "creative_insight_audience_activity_trigger" in activity_names
    assert "creative_concept_fanout_activity_trigger" in activity_names
    assert "creative_storyboard_render_activity_trigger" in activity_names
    assert "creative_package_handoff_activity_trigger" in activity_names


def test_orchestrator_short_circuits_on_brief_approval_reject():
    """A reject at ◆1 brief_approval halts the workflow before insight phase."""
    from api.functions.workflows.creative_campaign import creative_campaign_orchestration

    brief = {"id": "BRF-001", "client_brand": "Solene"}
    decisions = [
        {"decision": "approve", "transcript": "stub", "voice_score": 0.9},
        {"decision": "reject", "reason": "missing fields"},
    ]
    ctx = _FakeContext(brief=brief, decisions=decisions)

    gen = creative_campaign_orchestration(ctx)
    result = None
    sent = None
    while True:
        try:
            yielded = gen.send(sent) if sent is not None else next(gen)
        except StopIteration as stop:
            result = stop.value
            break
        if isinstance(yielded, _FakeTask):
            sent = yielded.result
        elif isinstance(yielded, dict):
            sent = yielded
        else:
            sent = yielded

    assert result is not None
    assert result["status"] == "rejected"
    assert result["phase"] == "brief_approval"
    # Insight & later activities did NOT run
    activity_names = [n for n, _ in ctx._calls if not n.startswith("checkpoint")]
    assert "creative_brief_synthesis_activity_trigger" in activity_names
    assert "creative_insight_audience_activity_trigger" not in activity_names
    assert "creative_concept_fanout_activity_trigger" not in activity_names
