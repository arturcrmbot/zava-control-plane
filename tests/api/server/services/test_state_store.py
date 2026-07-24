# tests/api/server/services/test_state_store.py
"""StateStore unit tests.

Lightweight coverage for the parts touched by POC2 §4.21 (AG-UI render
plan) — the per-workflow `agent_outputs` map and its `component_spec`
round-trip.
"""
from __future__ import annotations
import time

from api.server.services.state_store import StateStore
from api.shared.types import Workflow


def _make_workflow(workflow_id: str = "HIRE-1") -> Workflow:
    now = time.time()
    return Workflow(
        id=workflow_id,
        type="hiring",
        current_phase="Triage",
        created_at=now,
        sla_due_at=now + 86400,
        jurisdiction="London-Zava",
        agency="Zava-HR",
    )


def test_state_store_round_trips_component_spec():
    """POC2 §4.21: the StateStore preserves a `component_spec` array
    through the agent_outputs map so the FastAPI serialiser can lift it
    back into `/api/workflows/{id}` for WorkflowDetail to render."""
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-1"))

    spec = [
        {"kind": "fact_grid", "title": "Profile",
         "facts": [{"label": "Role", "value": "SDE"}]},
        {"kind": "skill_chips", "title": "Top skills",
         "skills": ["python", "spark"]},
    ]
    output = {
        "candidate_id": "C-SE-USA-00",
        "profile": {"current_title": "Senior Data Engineer"},
        "component_spec": spec,
        "inconsistencies": [],
    }
    store.append_agent_output("HIRE-1", "cv_crystalliser", output)

    w = store.get_workflow("HIRE-1")
    assert w is not None
    assert "cv_crystalliser" in w.agent_outputs
    assert w.agent_outputs["cv_crystalliser"]["component_spec"] == spec


def test_append_agent_output_replaces_prior_for_same_agent():
    """Re-runs of the same agent overwrite the prior output (last write
    wins per agent name) so the UI never renders stale specs."""
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-2"))

    store.append_agent_output("HIRE-2", "cv_crystalliser", {"component_spec": [{"kind": "callout", "tone": "info", "text": "first"}]})
    store.append_agent_output("HIRE-2", "cv_crystalliser", {"component_spec": [{"kind": "callout", "tone": "info", "text": "second"}]})

    w = store.get_workflow("HIRE-2")
    assert w is not None
    assert len(w.agent_outputs["cv_crystalliser"]["component_spec"]) == 1
    assert w.agent_outputs["cv_crystalliser"]["component_spec"][0]["text"] == "second"


def test_append_agent_output_no_op_when_workflow_unknown():
    """Agent outputs for unknown workflows have nowhere to land — silently
    drop rather than blow up the webhook handler."""
    store = StateStore()
    # No workflow registered — should not raise.
    store.append_agent_output("HIRE-NONEXISTENT", "cv_crystalliser", {"component_spec": []})
    assert store.get_workflow("HIRE-NONEXISTENT") is None


def test_get_agent_outputs_returns_copy():
    """Defensive copy — callers mutating the dict shouldn't corrupt store
    state."""
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-3"))
    store.append_agent_output("HIRE-3", "cv_crystalliser", {"component_spec": []})

    snap = store.get_agent_outputs("HIRE-3")
    snap["bogus"] = {"x": 1}

    w = store.get_workflow("HIRE-3")
    assert w is not None
    assert "bogus" not in w.agent_outputs


def test_agent_output_timestamp_is_parallel_to_the_domain_output_shape():
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-TIMESTAMP"))
    output = {
        "verdict": "green",
        "profile": {"current_title": "Senior Data Engineer"},
    }

    store.append_agent_output(
        "HIRE-TIMESTAMP",
        "cv_crystalliser",
        output,
        recorded_at=1_234.5,
    )

    assert store.get_agent_outputs("HIRE-TIMESTAMP") == {
        "cv_crystalliser": output,
    }
    assert store.get_agent_output_recorded_at(
        "HIRE-TIMESTAMP",
        "cv_crystalliser",
    ) == 1_234.5
    assert "recorded_at" not in output

    store.append_agent_output(
        "HIRE-TIMESTAMP",
        "cv_crystalliser",
        {"verdict": "amber"},
        recorded_at=1_235.5,
    )
    assert store.get_agent_output_recorded_at(
        "HIRE-TIMESTAMP",
        "cv_crystalliser",
    ) == 1_235.5
    assert store.get_agent_output_recorded_at(
        "HIRE-TIMESTAMP",
        "unknown-agent",
    ) is None


def test_replacing_workflow_clears_agent_output_timestamps():
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-REPLACED"))
    store.append_agent_output(
        "HIRE-REPLACED",
        "cv_crystalliser",
        {"verdict": "green"},
        recorded_at=1_234.5,
    )

    store.upsert_workflow(_make_workflow("HIRE-REPLACED"))

    assert store.get_agent_output_recorded_at(
        "HIRE-REPLACED",
        "cv_crystalliser",
    ) is None


def test_upserting_same_workflow_after_output_clear_removes_stale_timestamp():
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-CLEARED"))
    store.append_agent_output(
        "HIRE-CLEARED",
        "cv_crystalliser",
        {"verdict": "green"},
        recorded_at=1_234.5,
    )
    workflow = store.get_workflow("HIRE-CLEARED")
    assert workflow is not None
    workflow.agent_outputs.clear()

    store.upsert_workflow(workflow)

    assert store.get_agent_output_recorded_at(
        "HIRE-CLEARED",
        "cv_crystalliser",
    ) is None
    assert "_agentOutputRecordedAt" not in store.workflow_replay_patch(workflow)


def test_upsert_after_workflow_map_clear_does_not_reuse_orphaned_timestamp():
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-MAP-CLEARED"))
    store.append_agent_output(
        "HIRE-MAP-CLEARED",
        "cv_crystalliser",
        {"verdict": "old"},
        recorded_at=1_234.5,
    )
    store._workflows.clear()

    replacement = _make_workflow("HIRE-MAP-CLEARED")
    replacement.agent_outputs = {"cv_crystalliser": {"verdict": "replacement"}}
    store.upsert_workflow(replacement)

    assert store.get_agent_output_recorded_at(
        "HIRE-MAP-CLEARED",
        "cv_crystalliser",
    ) is None


def test_append_agent_output_strips_root_wrapper_private_tool_calls_with_one_copy():
    store = StateStore()
    store.upsert_workflow(_make_workflow("HIRE-SANITIZED"))
    output = {
        "verdict": "green",
        "summary": "Candidate evidence is complete.",
        "_raw_tool_calls": [{
            "tool": "candidate_lookup",
            "result": {"marker": "EXACT-TOOL-EVIDENCE"},
        }],
        "profile": {
            "headline": "Senior engineer",
            "_raw_tool_calls": [{"result": {"marker": "NESTED-EVIDENCE"}}],
        },
        "items": [
            {"value": 7, "_raw_tool_calls": [{"result": "LIST-EVIDENCE"}]},
        ],
    }

    store.append_agent_output(
        "HIRE-SANITIZED",
        "cv_crystalliser",
        output,
        recorded_at=1_234.5,
    )

    assert store.get_agent_outputs("HIRE-SANITIZED") == {
        "cv_crystalliser": {
            "verdict": "green",
            "summary": "Candidate evidence is complete.",
            "profile": {
                "headline": "Senior engineer",
                "_raw_tool_calls": [{"result": {"marker": "NESTED-EVIDENCE"}}],
            },
            "items": [
                {"value": 7, "_raw_tool_calls": [{"result": "LIST-EVIDENCE"}]},
            ],
        },
    }
    stored = store.get_agent_outputs("HIRE-SANITIZED")["cv_crystalliser"]
    assert stored is not output
    assert stored["profile"] is output["profile"]
    assert output["_raw_tool_calls"][0]["result"]["marker"] == "EXACT-TOOL-EVIDENCE"
    assert output["profile"]["_raw_tool_calls"][0]["result"]["marker"] == "NESTED-EVIDENCE"


def test_upsert_workflow_sanitizes_private_tool_calls_from_replay_state():
    store = StateStore()
    workflow = _make_workflow("HIRE-REPLAY-SANITIZED")
    workflow.agent_outputs = {
        "cv_crystalliser": {
            "_raw_tool_calls": [{"result": {"marker": "REPLAY-EVIDENCE"}}],
            "profile": {
                "headline": "Senior engineer",
            },
        },
    }

    store.upsert_workflow(workflow)

    assert store.get_agent_outputs("HIRE-REPLAY-SANITIZED") == {
        "cv_crystalliser": {
            "profile": {"headline": "Senior engineer"},
        },
    }
    assert (
        workflow.agent_outputs["cv_crystalliser"]["_raw_tool_calls"]
        [0]["result"]["marker"]
        == "REPLAY-EVIDENCE"
    )


def test_build_hiring_workflow_lifts_fixture_component_spec():
    """POC2 §4.21 fixture loader: hand-authored component_spec on a CV
    fixture must land on the workflow's agent_outputs.cv_crystalliser at
    build time so seeded HIRE-* workflows show the scorecard immediately,
    without waiting for a real Triage run."""
    from api.server.services.synthetic_data import build_hiring_workflow

    # C-SE-USA-00 was hand-authored with a 3-entry component_spec
    # (fact_grid, skill_chips, callout) per Task 4.
    w = build_hiring_workflow("HIRE-SMOKE-1", candidate_id="C-SE-USA-00")
    assert w.type == "hiring"
    assert "cv_crystalliser" in w.agent_outputs
    spec = w.agent_outputs["cv_crystalliser"]["component_spec"]
    assert isinstance(spec, list) and len(spec) >= 2
    kinds = [entry["kind"] for entry in spec]
    assert "fact_grid" in kinds
    assert "skill_chips" in kinds


def test_build_hiring_workflow_no_component_spec_when_fixture_lacks_it():
    """A fixture without component_spec must not synthesise an empty entry —
    the WorkflowDetail render path then leaves the scorecard hidden."""
    from api.server.services.synthetic_data import build_hiring_workflow

    # C-SE-DE-00 (or any non-hand-authored fixture) has no component_spec.
    w = build_hiring_workflow("HIRE-SMOKE-2", candidate_id="C-SE-DE-00")
    assert w.type == "hiring"
    assert "cv_crystalliser" not in w.agent_outputs
