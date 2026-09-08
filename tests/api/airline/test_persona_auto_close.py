"""Tests for duty_operations_manager persona auto-close contract.

Covers:
- SKILL.md loads via _load_personae (decision_policy present)
- Compiled decide(context) calls real authority seam, approves <=GBP150k
- Over-limit or wrong-action context does not approve
- hitl_context has canonical action/request fields
- Persona-generated event passes _approval_reason validation
"""
from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from api.server.services.governance.kernel import _reset_for_tests
from api.shared.vertical_loader import active_runtime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _airline_vertical(monkeypatch):
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    _reset_for_tests()
    try:
        yield
    finally:
        _reset_for_tests()
        active_runtime.cache_clear()


# ---------------------------------------------------------------------------
# Test: _load_personae picks up duty_operations_manager
# ---------------------------------------------------------------------------


def test_load_personae_includes_duty_operations_manager():
    from api.server.services import persona_responder

    # Reload to pick up modified SKILL.md
    defs = persona_responder._load_personae()
    assert "duty_operations_manager" in defs
    defn = defs["duty_operations_manager"]
    assert defn.external_event == "duty_operations_manager_decision"
    assert callable(defn.decide)


# ---------------------------------------------------------------------------
# Test: compiled decide() approves within authority (<=150k)
# ---------------------------------------------------------------------------


def test_persona_decide_approves_within_authority():
    from api.server.services import persona_responder

    defs = persona_responder._load_personae()
    decide = defs["duty_operations_manager"].decide

    context = {
        "action": "airline.commit_recovery_plan",
        "request": {"amount_gbp": 120000, "category": "synthetic-operational-recovery"},
        "workflow_id": "AIRHUB-0001",
        "story_id": "SYN-STORY-HUB-001",
        "decision_id": "SYN-DECISION-001",
        "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        "evidence_versions": {"SYN-SECTOR-IN-001": 3, "SYN-SECTOR-OUT-001": 2},
    }

    result = decide(context)
    assert result["decision"] == "approve"
    assert "duty_operations_manager" in result.get("persona", "")
    assert result.get("selected_option_id") == "SYN-OPTION-TAIL-CREW-STAND"
    assert result.get("evidence_versions") == context["evidence_versions"]
    assert result.get("decision_id") == "SYN-DECISION-001"


# ---------------------------------------------------------------------------
# Test: over-limit escalates
# ---------------------------------------------------------------------------


def test_persona_decide_escalates_over_limit():
    from api.server.services import persona_responder

    defs = persona_responder._load_personae()
    decide = defs["duty_operations_manager"].decide

    context = {
        "action": "airline.commit_recovery_plan",
        "request": {"amount_gbp": 200000, "category": "synthetic-operational-recovery"},
        "workflow_id": "AIRHUB-0001",
        "story_id": "SYN-STORY-HUB-001",
        "decision_id": "SYN-DECISION-001",
        "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        "evidence_versions": {},
    }

    result = decide(context)
    assert result["decision"] in ("escalate", "reject")
    assert result["decision"] != "approve"


# ---------------------------------------------------------------------------
# Test: missing/wrong action rejects
# ---------------------------------------------------------------------------


def test_persona_decide_rejects_missing_action():
    from api.server.services import persona_responder

    defs = persona_responder._load_personae()
    decide = defs["duty_operations_manager"].decide

    context = {
        "request": {"amount_gbp": 50000, "category": "synthetic-operational-recovery"},
    }

    result = decide(context)
    assert result["decision"] == "reject"


# ---------------------------------------------------------------------------
# Test: hitl_context has canonical action/request
# ---------------------------------------------------------------------------


def test_hitl_context_has_action_and_request(monkeypatch):
    import verticals.airline.durable as durable
    from verticals.airline.worlds.scenario import AirlineWorld
    from api.server.world.runtime import SimulationRuntime

    # Use real kernel for authority
    _REAL_KERNEL = durable.kernel

    runtime = SimulationRuntime(seed=42)
    world = AirlineWorld(seed=42, runtime=runtime)
    world.install()
    world.activate_scenario("synthetic-hub-cascade")

    sensor = next(
        e for e in runtime.journal
        if e.type == "sensor.tripped" and e.actor_id == "sensor:integrated_hub_disruption"
    )
    observation = world.build_observation(sensor.to_dict())
    observation["actor_ids"] = list(observation["evidence_versions"])
    observation["event_ids"] = list(observation["evidence_event_ids"])

    # Allow authority
    class _AllowKernel:
        def check_authority(self, **_kw):
            return SimpleNamespace(allowed=True, reason="test", governing_rule_id="T-001")

    monkeypatch.setattr(durable, "kernel", lambda: _AllowKernel())

    # Valid approval to avoid denial
    approval_payload = {
        "decision": "approve",
        "persona": "duty_operations_manager",
        "decision_id": "SYN-DECISION-001",
        "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        "evidence_versions": copy.deepcopy(observation["evidence_versions"]),
        "workflow_id": "AIRHUB-0001",
        "story_id": "SYN-STORY-HUB-001",
        "rationale": "test",
    }

    class _Task:
        def __init__(self, result=None):
            self.result = result
        def cancel(self):
            pass

    class _Ctx:
        instance_id = "airline-instance-1"
        from datetime import datetime
        current_utc_datetime = datetime(2026, 7, 28)

        def __init__(self):
            self.external_event = None
            self.calls = []

        def get_input(self):
            return {
                "workflow_id": "AIRHUB-0001",
                "type": "integrated-hub-disruption-recovery",
                "observation": copy.deepcopy(observation),
            }

        def call_activity(self, name, payload):
            self.calls.append((name, payload))
            if name == "airline_evidence_activity_trigger":
                return durable.airline_evidence_activity(payload)
            if name == "airline_agent_activity_trigger":
                return durable.airline_agent_activity(payload)
            if name == "airline_admission_activity_trigger":
                return durable.airline_admission_activity(payload)
            if name == "airline_governance_activity_trigger":
                return durable.airline_governance_activity(payload)
            if name == "airline_command_activity_trigger":
                return durable.airline_command_activity(payload, world=world)
            return {}

        def wait_for_external_event(self, name):
            self.external_event = name
            return _Task(approval_payload)

        def create_timer(self, _deadline):
            return _Task()

        def task_any(self, _tasks):
            return _Task(approval_payload)

    def _tool_call(name):
        return {
            "tool_call_id": f"call-{name}",
            "name": name,
            "tool": name,
            "args": "{}",
            "result": "{}",
            "success": True,
            "latency_ms": 0,
        }

    # Patch agent
    async def fake_agent(prompt, **kwargs):
        phase = kwargs["phase"]
        if phase == "Assess Network Impact":
            return {
                "phase": phase,
                "actor_ids": observation["actor_ids"],
                "event_ids": observation["event_ids"],
                "impact_summary": "test impact",
                "_raw_tool_calls": [_tool_call("airline_read_disruption_evidence")],
            }
        return {
            "phase": phase,
            "ranked_option_ids": ["SYN-OPTION-TAIL-CREW-STAND", "SYN-OPTION-CANCEL"],
            "reasoning": "test",
            "_raw_tool_calls": [_tool_call("airline_rank_feasible_recovery_options")],
        }

    monkeypatch.setattr(durable, "run_agent_session", fake_agent)

    # Drive orchestrator, capture checkpoints
    ctx = _Ctx()
    gen = durable.airline_orchestration(ctx)
    sent = None
    try:
        while True:
            yielded = gen.send(sent) if sent is not None else next(gen)
            sent = yielded
    except StopIteration:
        pass

    suspended = next(
        payload["payload"]
        for name, payload in ctx.calls
        if name == "checkpoint_activity_trigger" and payload.get("kind") == "suspended"
    )
    hitl_ctx = suspended["hitl_context"]
    assert hitl_ctx["action"] == "airline.commit_recovery_plan"
    assert hitl_ctx["request"]["amount_gbp"] > 0
    assert hitl_ctx["request"]["category"] == "synthetic-operational-recovery"


# ---------------------------------------------------------------------------
# Test: persona output passes _approval_reason (integration)
# ---------------------------------------------------------------------------


def test_persona_output_passes_approval_reason():
    """Compiled persona output (with extra fields) satisfies _approval_reason."""
    from api.server.services import persona_responder
    import verticals.airline.durable as durable

    defs = persona_responder._load_personae()
    decide = defs["duty_operations_manager"].decide

    evidence_versions = {"SYN-SECTOR-IN-001": 3, "SYN-SECTOR-OUT-001": 2}
    context = {
        "action": "airline.commit_recovery_plan",
        "request": {"amount_gbp": 120000, "category": "synthetic-operational-recovery"},
        "workflow_id": "AIRHUB-0001",
        "story_id": "SYN-STORY-HUB-001",
        "decision_id": "SYN-DECISION-001",
        "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        "evidence_versions": evidence_versions,
    }

    persona_result = decide(context)
    assert persona_result["decision"] == "approve"

    # Now verify _approval_reason accepts it
    selected_option = {"option_id": "SYN-OPTION-TAIL-CREW-STAND", "value_gbp": 120000}
    admitted_options = [
        {"option_id": "SYN-OPTION-TAIL-CREW-STAND"},
        {"option_id": "SYN-OPTION-CANCEL"},
    ]

    denial = durable._approval_reason(
        persona_result,
        workflow_id="AIRHUB-0001",
        selected_option=selected_option,
        admitted_options=admitted_options,
        evidence_versions=evidence_versions,
    )
    assert denial is None, f"Expected no denial but got: {denial}"


def test_persona_output_rejected_when_stale_evidence():
    """Stale evidence_versions still rejected even if persona approves."""
    from api.server.services import persona_responder
    import verticals.airline.durable as durable

    defs = persona_responder._load_personae()
    decide = defs["duty_operations_manager"].decide

    context = {
        "action": "airline.commit_recovery_plan",
        "request": {"amount_gbp": 120000, "category": "synthetic-operational-recovery"},
        "workflow_id": "AIRHUB-0001",
        "story_id": "SYN-STORY-HUB-001",
        "decision_id": "SYN-DECISION-001",
        "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        "evidence_versions": {"SYN-SECTOR-IN-001": 1},  # stale
    }

    persona_result = decide(context)
    assert persona_result["decision"] == "approve"

    # _approval_reason should reject because evidence doesn't match
    selected_option = {"option_id": "SYN-OPTION-TAIL-CREW-STAND", "value_gbp": 120000}
    admitted_options = [{"option_id": "SYN-OPTION-TAIL-CREW-STAND"}]
    real_evidence = {"SYN-SECTOR-IN-001": 3, "SYN-SECTOR-OUT-001": 2}

    denial = durable._approval_reason(
        persona_result,
        workflow_id="AIRHUB-0001",
        selected_option=selected_option,
        admitted_options=admitted_options,
        evidence_versions=real_evidence,
    )
    assert denial is not None
    assert "evidence" in denial.lower()
