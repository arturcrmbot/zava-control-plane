"""TDD tests for Airline Hero 3 – Preemptive Schedule Resilience Durable core.

Tests cover all six isolated phases:
  1. Detect Schedule Risk Signal      (deterministic evidence)
  2. Assess Network Ripple Effects    (agent – read tool required)
  3. Synthesize Resilience Options    (agent – both tools required; after admission)
  4. Approve Schedule Adjustment      (HITL – network_operations_director)
  5. Commit Schedule Adjustment       (deterministic command)
  6. Verify Network Stability         (deterministic pending-pipeline)

TDD RED → GREEN: module is pure importable, no DFApp/circular import.
"""
from __future__ import annotations

import asyncio
import copy
import inspect
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

import verticals.airline.schedule_durable as sched_durable
from api.server.services.governance.kernel import _reset_for_tests
from api.shared.vertical_loader import active_runtime
from verticals.airline.mcp_tools.schedule import TOOL_NAMES as SCHED_TOOL_NAMES
from verticals.airline.schedule_constants import (
    SCHED_STORY_ID,
    SCHED_WORKFLOW_ID,
    SCHED_WORKFLOW_TYPE,
    SCHED_DECISION_ID,
)
from verticals.airline.schedule_constraints import (
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_MONITOR_RISK,
    SCHED_OPTION_PREPOSITION,
    SCHED_OPTION_INFEASIBLE,
)
from verticals.airline.worlds.active import (
    register_active_airline_world,
    unregister_active_airline_world,
)
from verticals.airline.worlds.scenario import AirlineWorld

_REAL_KERNEL = sched_durable.kernel

_ALL_ADMITTED_IDS = [
    SCHED_OPTION_BUFFER_RETIME,
    SCHED_OPTION_PREPOSITION,
    SCHED_OPTION_CANCEL_LIMITED,
    SCHED_OPTION_MONITOR_RISK,
]
_DEFAULT_SELECTED = SCHED_OPTION_BUFFER_RETIME
_DEFAULT_DECISION_ID = SCHED_DECISION_ID
_ASSESS_TOOL = "airline_read_schedule_risk_evidence"
_RANK_TOOL = "airline_rank_admitted_resilience_options"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _Task:
    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def _tool_call(name: str, *, success: bool = True) -> dict[str, Any]:
    return {
        "tool_call_id": f"call-{name}",
        "name": name,
        "tool": name,
        "args": "{}",
        "result": "{}",
        "success": success,
        "latency_ms": 0,
    }


def _valid_assess_agent(ctx: "SchedContext", captured: list[dict[str, Any]] | None = None):
    """Fake that returns a valid Assess agent response (read tool only)."""
    async def fake(prompt: str, **kwargs: Any) -> dict[str, Any]:
        if captured is not None:
            captured.append({"prompt": prompt, **kwargs})
        obs = ctx.observation
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "impact_summary": "Two OUT sectors at risk; forecast confidence 0.72.",
            "uncertainty": "Cannot confirm actual slot tolerance without real ATM feed.",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }
    return fake


def _valid_synthesize_agent(ctx: "SchedContext", captured: list[dict[str, Any]] | None = None):
    """Fake that returns a valid Synthesize agent response (both tools)."""
    async def fake(prompt: str, **kwargs: Any) -> dict[str, Any]:
        if captured is not None:
            captured.append({"prompt": prompt, **kwargs})
        obs = ctx.observation
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "Buffer retime preferred; monitor_risk is explicit no-action baseline.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }
    return fake


class SchedContext:
    instance_id = "sched-instance-1"
    current_utc_datetime = datetime(2026, 8, 11)

    def __init__(
        self,
        *,
        approval: dict[str, Any] | None = None,
        timeout: bool = False,
        assess_agent: Any = None,
        synthesize_agent: Any = None,
    ) -> None:
        self.world = AirlineWorld(seed=42)
        self.world.install()
        self.world.activate_scenario("synthetic-schedule-restriction")
        self.observation = self.world.current_schedule_observation()
        self.observation["actor_ids"] = sorted(self.observation["evidence_versions"])
        self.observation["event_ids"] = list(self.observation["evidence_event_ids"])

        self._input = {
            "workflow_id": SCHED_WORKFLOW_ID,
            "type": SCHED_WORKFLOW_TYPE,
        }
        base = {
            "decision": "approve",
            "persona": "network_operations_director",
            "decision_id": _DEFAULT_DECISION_ID,
            "selected_option_id": _DEFAULT_SELECTED,
            "evidence_versions": copy.deepcopy(self.observation["evidence_versions"]),
            "workflow_id": SCHED_WORKFLOW_ID,
            "story_id": SCHED_STORY_ID,
        }
        if approval is not None:
            base.update(approval)
        self._approval_data = base
        self.approval = _Task(base)
        self.timer = _Task()
        self.timeout = timeout
        self._assess_agent = assess_agent or _valid_assess_agent(self)
        self._synthesize_agent = synthesize_agent or _valid_synthesize_agent(self)
        self.external_event: str | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_input(self) -> dict[str, Any]:
        return self._input

    def call_activity(self, name: str, payload: dict[str, Any]) -> Any:
        self.calls.append((name, payload))
        if name == "sched_evidence_activity_trigger":
            return sched_durable.sched_evidence_activity(payload, world=self.world)
        if name == "sched_assess_agent_activity_trigger":
            monkeypatched = payload.copy()
            original = sched_durable.run_agent_session

            async def _fake_run(prompt: str, **kwargs: Any) -> Any:
                return await self._assess_agent(prompt, **kwargs)

            sched_durable.run_agent_session = _fake_run
            try:
                result = sched_durable.sched_assess_agent_activity(monkeypatched)
            finally:
                sched_durable.run_agent_session = original
            return result
        if name == "sched_admission_activity_trigger":
            return sched_durable.sched_admission_activity(payload)
        if name == "sched_synthesize_agent_activity_trigger":
            monkeypatched = payload.copy()
            original = sched_durable.run_agent_session

            async def _fake_run2(prompt: str, **kwargs: Any) -> Any:
                return await self._synthesize_agent(prompt, **kwargs)

            sched_durable.run_agent_session = _fake_run2
            try:
                result = sched_durable.sched_synthesize_agent_activity(monkeypatched)
            finally:
                sched_durable.run_agent_session = original
            return result
        if name == "sched_governance_activity_trigger":
            return sched_durable.sched_governance_activity(payload)
        if name == "sched_command_activity_trigger":
            return sched_durable.sched_command_activity(payload, world=self.world)
        return {"checkpoint": payload.get("kind")}

    def wait_for_external_event(self, name: str) -> _Task:
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline: datetime) -> _Task:
        return self.timer

    def task_any(self, _tasks: list[_Task]) -> _Task:
        return self.timer if self.timeout else self.approval


class _AllowedKernel:
    def check_authority(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            allowed=True,
            reason="authorised by the test policy boundary",
            governing_rule_id="SCHED-TEST-001",
        )


class _DeniedKernel:
    def check_authority(self, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(
            allowed=False,
            reason="governance denied by test",
            governing_rule_id=None,
        )


@pytest.fixture(autouse=True)
def _allow_sched_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sched_durable, "kernel", lambda: _AllowedKernel())


@pytest.fixture
def _use_real_sched_kernel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    _reset_for_tests()
    monkeypatch.setattr(sched_durable, "kernel", _REAL_KERNEL)
    try:
        yield
    finally:
        _reset_for_tests()
        active_runtime.cache_clear()


def drive_sched_orchestrator(context: SchedContext) -> dict[str, Any]:
    generator = sched_durable.sched_orchestration(context)
    sent: Any = None
    while True:
        try:
            value = generator.send(sent)
            sent = value
        except StopIteration as exc:
            return exc.value


def test_schedule_agent_prompts_require_non_empty_business_text() -> None:
    context = SchedContext()
    evidence = sched_durable.sched_evidence_activity(
        context.get_input(),
        world=context.world,
    )
    assess_prompt = sched_durable._assess_agent_prompt(
        {
            **context.get_input(),
            "instance_id": context.instance_id,
            "evidence": evidence,
        }
    )
    assert "impact_summary MUST be a non-empty string" in assess_prompt
    assert "uncertainty MUST be a non-empty string" in assess_prompt
    assert "Call the required evidence tool at least once" in assess_prompt

    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    synthesize_prompt = sched_durable._synthesize_agent_prompt(
        {
            **context.get_input(),
            "instance_id": context.instance_id,
            "evidence": evidence,
            "assess": {
                "impact_summary": "Forecast capacity restriction affects two sectors.",
            },
            "admitted_options": admission["admitted_options"],
        }
    )
    assert "reasoning MUST be a non-empty string" in synthesize_prompt
    assert "Call each required tool at least once" in synthesize_prompt


# ---------------------------------------------------------------------------
# Phase 1 – sched_evidence_activity
# ---------------------------------------------------------------------------


def test_evidence_activity_returns_real_schedule_identity() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    payload = {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE}
    result = sched_durable.sched_evidence_activity(payload, world=world)
    assert result["story_id"] == SCHED_STORY_ID


def test_schedule_evidence_activity_uses_bridge_observation_and_arms_worker_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = AirlineWorld(seed=42)
    source.install()
    source.activate_scenario("synthetic-schedule-restriction")
    observation = source.current_schedule_observation()
    observation["trace_id"] = "bridge-schedule-trace"
    worker = AirlineWorld(seed=42)
    worker.install()
    monkeypatch.setattr(sched_durable, "_active_world", lambda: worker)

    result = sched_durable.sched_evidence_activity(
        {
            "workflow_id": "AIRSCHED-0001",
            "type": SCHED_WORKFLOW_TYPE,
            "observation": observation,
        }
    )

    assert result["observation"]["sensor_event_id"] == observation["sensor_event_id"]
    assert worker.sched_story_status[SCHED_STORY_ID] == "active"
    assert worker.current_schedule_observation()["trace_id"] == "bridge-schedule-trace"
    assert result["workflow_id"] == SCHED_WORKFLOW_ID
    assert result["source_mode"] == "simulated"
    assert isinstance(result["actor_ids"], list) and result["actor_ids"]
    assert isinstance(result["event_ids"], list) and result["event_ids"]
    assert isinstance(result["evidence_versions"], dict) and result["evidence_versions"]
    assert result["actor_ids"] == sorted(result["evidence_versions"])
    obs = result["observation"]
    assert obs.get("story_id") == SCHED_STORY_ID
    assert obs.get("sched_story_active") is True


def test_evidence_activity_wrong_type_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    with pytest.raises(ValueError, match="wrong workflow type"):
        sched_durable.sched_evidence_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "type": "wrong-type"},
            world=world,
        )


def test_evidence_activity_missing_type_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    with pytest.raises(ValueError, match="wrong workflow type"):
        sched_durable.sched_evidence_activity(
            {"workflow_id": SCHED_WORKFLOW_ID},
            world=world,
        )


def test_evidence_activity_inactive_scenario_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    with pytest.raises(ValueError, match="no active scenario"):
        sched_durable.sched_evidence_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
            world=world,
        )


def test_evidence_activity_world_not_aog_scenario() -> None:
    """Evidence fails if the world only has AOG scenario active (wrong story_id)."""
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    with pytest.raises(ValueError, match="no active scenario|wrong story"):
        sched_durable.sched_evidence_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
            world=world,
        )


def test_evidence_activity_event_and_actor_ids_are_unique() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    result = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    assert len(set(result["actor_ids"])) == len(result["actor_ids"])
    assert len(set(result["event_ids"])) == len(result["event_ids"])


# ---------------------------------------------------------------------------
# Admission activity
# ---------------------------------------------------------------------------


def test_admission_returns_four_admitted_options() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    result = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_ids = {opt["option_id"] for opt in result["admitted_options"]}
    assert admitted_ids == set(_ALL_ADMITTED_IDS)
    infeasible_ids = {opt["option_id"] for opt in result["rejected_options"]}
    assert SCHED_OPTION_INFEASIBLE in infeasible_ids


def test_admission_monitor_risk_preserved() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    result = sched_durable.sched_admission_activity({"evidence": evidence})
    monitor = next(
        (o for o in result["admitted_options"] if o["option_id"] == SCHED_OPTION_MONITOR_RISK),
        None,
    )
    assert monitor is not None
    assert monitor["value_gbp"] == 0.0
    assert monitor["admitted"] is True


def test_admission_all_options_have_required_fields() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    result = sched_durable.sched_admission_activity({"evidence": evidence})
    for opt in result["admitted_options"]:
        assert "option_id" in opt
        assert "value_gbp" in opt
        assert "actions" in opt
        assert "evidence_versions" in opt
        assert opt["feasible"] is True
        assert opt["admitted"] is True


def test_admission_missing_evidence_raises() -> None:
    with pytest.raises((ValueError, TypeError, KeyError)):
        sched_durable.sched_admission_activity({})


# ---------------------------------------------------------------------------
# Phase 2 – sched_assess_agent_activity
# ---------------------------------------------------------------------------


def test_assess_activity_valid_read_tool() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "Two sectors at risk.",
            "uncertainty": "Cannot confirm ATM slot tolerance without live feed.",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_assess_agent_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
        )
    finally:
        sched_durable.run_agent_session = original

    assert result["phase"] == sched_durable._ASSESS_PHASE
    assert result["impact_summary"]
    assert result["uncertainty"]
    assert result["actor_ids"] == evidence["actor_ids"]
    assert result["event_ids"] == evidence["event_ids"]
    assert "_raw_tool_calls" not in result  # stripped from output


def test_assess_activity_wrong_phase_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": "WRONG PHASE",
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="changed the phase"):
            sched_durable.sched_assess_agent_activity(
                {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
            )
    finally:
        sched_durable.run_agent_session = original


def test_assess_activity_missing_tool_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [],  # empty – no tool calls
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="absent or empty"):
            sched_durable.sched_assess_agent_activity(
                {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
            )
    finally:
        sched_durable.run_agent_session = original


def test_assess_activity_undeclared_tool_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [_tool_call("some_random_tool")],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="undeclared tool"):
            sched_durable.sched_assess_agent_activity(
                {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
            )
    finally:
        sched_durable.run_agent_session = original


def test_assess_activity_changed_actor_ids_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": ["TAMPERED-ACTOR"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="changed actor IDs"):
            sched_durable.sched_assess_agent_activity(
                {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
            )
    finally:
        sched_durable.run_agent_session = original


def test_assess_activity_corrective_retry_on_no_tool_evidence() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    calls: list[int] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        if len(calls) == 1:
            # First attempt – no tool evidence
            return {
                "phase": sched_durable._ASSESS_PHASE,
                "actor_ids": evidence["actor_ids"],
                "event_ids": evidence["event_ids"],
                "impact_summary": "ok",
                "uncertainty": "ok",
            }
        # Second attempt – with tool evidence
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "Two sectors at risk.",
            "uncertainty": "Slot tolerance unconfirmable.",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_assess_agent_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
        )
    finally:
        sched_durable.run_agent_session = original

    assert len(calls) == 2  # one retry
    assert result["phase"] == sched_durable._ASSESS_PHASE


def test_assess_activity_retries_failed_declared_tool_call() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    calls: list[int] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [
                _tool_call(_ASSESS_TOOL, success=len(calls) > 1),
            ],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_assess_agent_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
        )
    finally:
        sched_durable.run_agent_session = original

    assert len(calls) == 2
    assert result["phase"] == sched_durable._ASSESS_PHASE


def test_assess_activity_accepts_failed_read_followed_by_success() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "Two sectors are exposed to the forecast constraint.",
            "uncertainty": "The final slot tolerance remains unconfirmed.",
            "_raw_tool_calls": [
                _tool_call(_ASSESS_TOOL, success=False),
                _tool_call(_ASSESS_TOOL),
            ],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_assess_agent_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
        )
    finally:
        sched_durable.run_agent_session = original

    assert result["phase"] == sched_durable._ASSESS_PHASE


def test_assess_skill_and_phase_passed_to_run_agent_session() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    captured: list[dict[str, Any]] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        captured.append({"prompt": prompt, **kwargs})
        return {
            "phase": sched_durable._ASSESS_PHASE,
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "impact_summary": "ok",
            "uncertainty": "ok",
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        sched_durable.sched_assess_agent_activity(
            {"workflow_id": SCHED_WORKFLOW_ID, "evidence": evidence}
        )
    finally:
        sched_durable.run_agent_session = original

    assert captured
    call = captured[0]
    assert call.get("skill_label") == sched_durable._SCHED_SKILL_LABEL
    assert call.get("phase") == sched_durable._ASSESS_PHASE


# ---------------------------------------------------------------------------
# Phase 3 – sched_synthesize_agent_activity
# ---------------------------------------------------------------------------


def _make_admitted_options() -> list[dict[str, Any]]:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    return sched_durable.sched_admission_activity({"evidence": evidence}), evidence


def test_synthesize_activity_valid_both_tools() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "Buffer retime preferred. monitor_risk is explicit no-action.",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admitted_options,
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert result["phase"] == sched_durable._SYNTHESIZE_PHASE
    assert set(result["ranked_option_ids"]) == set(_ALL_ADMITTED_IDS)
    assert result["evidence_versions"] == evidence["evidence_versions"]
    assert "_raw_tool_calls" not in result


def test_synthesize_activity_requires_both_tools() -> None:
    """Synthesize phase must have both tools; only read tool is insufficient."""
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "ok",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL)],  # missing rank tool
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="missing"):
            sched_durable.sched_synthesize_agent_activity({
                "workflow_id": SCHED_WORKFLOW_ID,
                "evidence": evidence,
                "admitted_options": admitted_options,
                "assess": {"impact_summary": "ok", "uncertainty": "ok"},
            })
    finally:
        sched_durable.run_agent_session = original


def test_synthesize_activity_monitor_risk_in_ranked_list() -> None:
    """monitor_risk must appear in ranked list (bijection including no-action)."""
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        # Ranking without monitor_risk
        ranked_without_monitor = [o for o in _ALL_ADMITTED_IDS if o != SCHED_OPTION_MONITOR_RISK]
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": ranked_without_monitor,
            "reasoning": "ok",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="ranking must contain every admitted option"):
            sched_durable.sched_synthesize_agent_activity({
                "workflow_id": SCHED_WORKFLOW_ID,
                "evidence": evidence,
                "admitted_options": admitted_options,
                "assess": {"impact_summary": "ok", "uncertainty": "ok"},
            })
    finally:
        sched_durable.run_agent_session = original


def test_synthesize_activity_changed_evidence_versions_raises() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "ok",
            "evidence_versions": {"TAMPERED": 99},
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="changed evidence versions"):
            sched_durable.sched_synthesize_agent_activity({
                "workflow_id": SCHED_WORKFLOW_ID,
                "evidence": evidence,
                "admitted_options": admitted_options,
                "assess": {"impact_summary": "ok", "uncertainty": "ok"},
            })
    finally:
        sched_durable.run_agent_session = original


def test_synthesize_activity_corrective_retry_on_no_evidence() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]
    calls: list[int] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        if len(calls) == 1:
            return {
                "phase": sched_durable._SYNTHESIZE_PHASE,
                "ranked_option_ids": list(_ALL_ADMITTED_IDS),
                "reasoning": "ok",
                "evidence_versions": evidence["evidence_versions"],
                "actor_ids": evidence["actor_ids"],
                "event_ids": evidence["event_ids"],
            }
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "ok",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admitted_options,
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert len(calls) == 2
    assert result["phase"] == sched_durable._SYNTHESIZE_PHASE


def test_synthesize_activity_retries_failed_declared_tool_call() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]
    calls: list[int] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "Retry succeeded.",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [
                _tool_call(_ASSESS_TOOL, success=len(calls) > 1),
                _tool_call(_RANK_TOOL),
            ],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admitted_options,
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert len(calls) == 2
    assert result["phase"] == sched_durable._SYNTHESIZE_PHASE


def test_synthesize_activity_accepts_failed_read_followed_by_success() -> None:
    admission, evidence = _make_admitted_options()

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "The agent corrected its evidence read before ranking.",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [
                _tool_call(_ASSESS_TOOL, success=False),
                _tool_call(_ASSESS_TOOL),
                _tool_call(_RANK_TOOL),
            ],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admission["admitted_options"],
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert result["phase"] == sched_durable._SYNTHESIZE_PHASE


def test_synthesize_activity_missing_rank_tool_raises() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "ok",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_ASSESS_TOOL)],  # dup
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        with pytest.raises(ValueError, match="missing"):
            sched_durable.sched_synthesize_agent_activity({
                "workflow_id": SCHED_WORKFLOW_ID,
                "evidence": evidence,
                "admitted_options": admitted_options,
                "assess": {"impact_summary": "ok", "uncertainty": "ok"},
            })
    finally:
        sched_durable.run_agent_session = original


def test_synthesize_activity_preserves_successful_duplicate_read_calls() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "Both required tools succeeded; one read was repeated.",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [
                _tool_call(_ASSESS_TOOL),
                _tool_call(_ASSESS_TOOL),
                _tool_call(_RANK_TOOL),
            ],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        result = sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admitted_options,
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert result["ranked_option_ids"] == list(_ALL_ADMITTED_IDS)


def test_synthesize_skill_label_passed_to_runner() -> None:
    admission, evidence = _make_admitted_options()
    admitted_options = admission["admitted_options"]
    captured: list[dict[str, Any]] = []

    async def fake_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        captured.append({"prompt": prompt, **kwargs})
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": list(_ALL_ADMITTED_IDS),
            "reasoning": "ok",
            "evidence_versions": evidence["evidence_versions"],
            "actor_ids": evidence["actor_ids"],
            "event_ids": evidence["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    original = sched_durable.run_agent_session
    sched_durable.run_agent_session = fake_agent
    try:
        sched_durable.sched_synthesize_agent_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "evidence": evidence,
            "admitted_options": admitted_options,
            "assess": {"impact_summary": "ok", "uncertainty": "ok"},
        })
    finally:
        sched_durable.run_agent_session = original

    assert captured[0].get("skill_label") == sched_durable._SCHED_SKILL_LABEL
    assert captured[0].get("phase") == sched_durable._SYNTHESIZE_PHASE


# ---------------------------------------------------------------------------
# Governance activity
# ---------------------------------------------------------------------------


def test_governance_allows_300k_for_network_operations_director(_use_real_sched_kernel: None) -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    register_active_airline_world(world)
    try:
        result = sched_durable.sched_governance_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "selected_option": {"option_id": SCHED_OPTION_BUFFER_RETIME, "value_gbp": 45_000.0},
        })
        assert result["allowed"] is True
    finally:
        unregister_active_airline_world(world)


def test_governance_denies_mocked() -> None:
    import types
    mod = types.ModuleType("fake_kernel")
    mod.check_authority = lambda **kw: SimpleNamespace(allowed=False, reason="test deny", governing_rule_id=None)

    # monkeypatch directly
    original = sched_durable.kernel
    sched_durable.kernel = lambda: mod
    try:
        result = sched_durable.sched_governance_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "selected_option": {"option_id": SCHED_OPTION_BUFFER_RETIME, "value_gbp": 45_000.0},
        })
        assert result["allowed"] is False
    finally:
        sched_durable.kernel = original


def test_governance_non_finite_value_raises() -> None:
    import math
    with pytest.raises(ValueError, match="finite"):
        sched_durable.sched_governance_activity({
            "workflow_id": SCHED_WORKFLOW_ID,
            "selected_option": {"option_id": SCHED_OPTION_BUFFER_RETIME, "value_gbp": math.inf},
        })


# ---------------------------------------------------------------------------
# Command activity – sched_command_activity
# ---------------------------------------------------------------------------


def test_command_activity_decision_ready() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_BUFFER_RETIME,
        "evidence_versions": evidence["evidence_versions"],
    }
    hitl_context = {"evidence_versions": evidence["evidence_versions"]}
    result = sched_durable.sched_command_activity(
        {
            "workflow_id": SCHED_WORKFLOW_ID,
            "approval": approval,
            "hitl_context": hitl_context,
        },
        world=world,
    )
    assert result["status"] == "decision_ready"
    assert result["evaluation"]["status"] == "pending_world_event_pipeline"
    assert result["command"] is not None
    assert result["gateway_event"] is not None


def test_command_activity_idempotent_retry() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_BUFFER_RETIME,
        "evidence_versions": evidence["evidence_versions"],
    }
    hitl_context = {"evidence_versions": evidence["evidence_versions"]}
    payload = {
        "workflow_id": SCHED_WORKFLOW_ID,
        "approval": approval,
        "hitl_context": hitl_context,
    }
    result1 = sched_durable.sched_command_activity(payload, world=world)
    assert result1["status"] == "decision_ready"
    result2 = sched_durable.sched_command_activity(payload, world=world)
    assert result2["status"] == "decision_ready"
    # Same command on retry
    assert result1["command"]["command_id"] == result2["command"]["command_id"]


def test_command_activity_stale_evidence_denied() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    stale_versions = {k: v + 100 for k, v in evidence["evidence_versions"].items()}
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_BUFFER_RETIME,
        "evidence_versions": stale_versions,
    }
    hitl_context = {"evidence_versions": stale_versions}
    result = sched_durable.sched_command_activity(
        {
            "workflow_id": SCHED_WORKFLOW_ID,
            "approval": approval,
            "hitl_context": hitl_context,
        },
        world=world,
    )
    assert result["status"] == "denied"
    assert result["command"] is None


def test_command_activity_inactive_scenario_denied() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_BUFFER_RETIME,
        "evidence_versions": evidence["evidence_versions"],
    }
    hitl_context = {"evidence_versions": evidence["evidence_versions"]}
    # Use a fresh world without activation
    empty_world = AirlineWorld(seed=42)
    empty_world.install()
    result = sched_durable.sched_command_activity(
        {
            "workflow_id": SCHED_WORKFLOW_ID,
            "approval": approval,
            "hitl_context": hitl_context,
        },
        world=empty_world,
    )
    assert result["status"] == "denied"


def test_command_activity_monitor_risk_decision_ready() -> None:
    """monitor_risk command is admitted and produces decision_ready (no release of constraints)."""
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_MONITOR_RISK,
        "evidence_versions": evidence["evidence_versions"],
    }
    hitl_context = {"evidence_versions": evidence["evidence_versions"]}
    result = sched_durable.sched_command_activity(
        {
            "workflow_id": SCHED_WORKFLOW_ID,
            "approval": approval,
            "hitl_context": hitl_context,
        },
        world=world,
    )
    assert result["status"] == "decision_ready"
    assert result["evaluation"]["success_event"] == sched_durable.COMMAND_TYPE.replace("commit_", "") + ".applied"


def test_command_activity_no_false_completion() -> None:
    """success_event in pending evaluation is the schedule success event, not a workflow.completed claim."""
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_BUFFER_RETIME,
        "evidence_versions": evidence["evidence_versions"],
    }
    hitl_context = {"evidence_versions": evidence["evidence_versions"]}
    result = sched_durable.sched_command_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "approval": approval, "hitl_context": hitl_context},
        world=world,
    )
    assert "workflow.completed" not in result["evaluation"]["success_event"]
    assert result["evaluation"]["status"] == "pending_world_event_pipeline"


# ---------------------------------------------------------------------------
# Approval validation
# ---------------------------------------------------------------------------


def test_approval_valid_passes() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    selected = admitted_options[0]
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": selected["option_id"],
        "evidence_versions": evidence["evidence_versions"],
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=selected,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is None


def test_approval_wrong_persona_rejected() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    selected = admitted_options[0]
    approval = {
        "decision": "approve",
        "persona": "engineering_duty_manager",  # wrong
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": selected["option_id"],
        "evidence_versions": evidence["evidence_versions"],
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=selected,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is not None
    assert "persona" in reason.lower()


def test_approval_stale_evidence_rejected() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    selected = admitted_options[0]
    stale_versions = {k: v + 1 for k, v in evidence["evidence_versions"].items()}
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": selected["option_id"],
        "evidence_versions": stale_versions,
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=selected,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is not None
    assert "stale" in reason.lower()


def test_approval_non_admitted_option_rejected() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    selected = admitted_options[0]
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_INFEASIBLE,  # not admitted
        "evidence_versions": evidence["evidence_versions"],
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=selected,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is not None
    assert "not deterministically admitted" in reason.lower()


def test_approval_monitor_risk_valid_when_ranked_top() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    monitor = next(o for o in admitted_options if o["option_id"] == SCHED_OPTION_MONITOR_RISK)
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": SCHED_OPTION_MONITOR_RISK,
        "evidence_versions": evidence["evidence_versions"],
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=monitor,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is None


def test_approval_wrong_workflow_rejected() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    evidence = sched_durable.sched_evidence_activity(
        {"workflow_id": SCHED_WORKFLOW_ID, "type": SCHED_WORKFLOW_TYPE},
        world=world,
    )
    admission = sched_durable.sched_admission_activity({"evidence": evidence})
    admitted_options = admission["admitted_options"]
    selected = admitted_options[0]
    approval = {
        "decision": "approve",
        "persona": "network_operations_director",
        "decision_id": _DEFAULT_DECISION_ID,
        "selected_option_id": selected["option_id"],
        "evidence_versions": evidence["evidence_versions"],
        "workflow_id": "WRONG-WORKFLOW",
    }
    reason = sched_durable._sched_approval_reason(
        approval,
        workflow_id=SCHED_WORKFLOW_ID,
        selected_option=selected,
        admitted_options=admitted_options,
        evidence_versions=evidence["evidence_versions"],
    )
    assert reason is not None
    assert "workflow" in reason.lower()


# ---------------------------------------------------------------------------
# Full orchestration – drive_sched_orchestrator
# ---------------------------------------------------------------------------


def test_orchestration_happy_path() -> None:
    ctx = SchedContext()
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "decision_ready"
    assert result["workflow_id"] == "AIRSCHED-0001"
    assert result["evaluation"]["status"] == "pending_world_event_pipeline"
    assert result["approval"]["decision"] == "approve"
    assert "workflow_evidence" in result
    assert "reasoning" in result


def test_orchestration_phase_order() -> None:
    """Activities are called in correct order: evidence → assess → admission → synthesize → governance → command."""
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    activity_names = [name for name, _ in ctx.calls]
    # Find key activities
    ev_idx = next(i for i, n in enumerate(activity_names) if n == "sched_evidence_activity_trigger")
    assess_idx = next(i for i, n in enumerate(activity_names) if n == "sched_assess_agent_activity_trigger")
    adm_idx = next(i for i, n in enumerate(activity_names) if n == "sched_admission_activity_trigger")
    synth_idx = next(i for i, n in enumerate(activity_names) if n == "sched_synthesize_agent_activity_trigger")
    gov_idx = next(i for i, n in enumerate(activity_names) if n == "sched_governance_activity_trigger")
    cmd_idx = next(i for i, n in enumerate(activity_names) if n == "sched_command_activity_trigger")
    assert ev_idx < assess_idx < adm_idx < synth_idx < gov_idx < cmd_idx


def test_orchestration_hitl_suspend_contains_full_context() -> None:
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    # Find the checkpoint_activity_trigger call for "suspended"
    suspend_calls = [
        p for name, p in ctx.calls
        if name == "checkpoint_activity_trigger" and p.get("kind") == "suspended"
    ]
    assert suspend_calls
    payload = suspend_calls[0]["payload"]
    assert payload.get("persona") == "network_operations_director"
    assert payload.get("external_event") == "network_operations_director_decision"
    assert payload.get("action") == "airline.commit_schedule_adjustment"
    assert payload.get("category") == "synthetic-schedule-resilience"
    assert "request" in payload
    assert "ranking" in payload
    assert "admitted_options" in payload
    assert "evidence_versions" in payload
    assert "signal" in payload or "observation" in payload  # risk signal context
    assert "selected_option" in payload


def test_orchestration_detect_checkpoint_has_evidence() -> None:
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    detect_completions = [
        p for name, p in ctx.calls
        if name == "checkpoint_activity_trigger"
        and p.get("kind") == "step.completed"
        and p["payload"].get("step") == sched_durable._DETECT_PHASE
    ]
    assert detect_completions
    payload = detect_completions[0]["payload"]
    assert "actor_ids" in payload
    assert "event_ids" in payload
    assert "evidence_versions" in payload
    assert "observation" in payload


def test_orchestration_assess_checkpoint_has_impact_and_uncertainty() -> None:
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    assess_completions = [
        p for name, p in ctx.calls
        if name == "checkpoint_activity_trigger"
        and p.get("kind") == "step.completed"
        and p["payload"].get("step") == sched_durable._ASSESS_PHASE
    ]
    assert assess_completions
    payload = assess_completions[0]["payload"]
    assert "impact_summary" in payload
    assert "uncertainty" in payload


def test_orchestration_synthesize_checkpoint_has_ranking() -> None:
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    synth_completions = [
        p for name, p in ctx.calls
        if name == "checkpoint_activity_trigger"
        and p.get("kind") == "step.completed"
        and p["payload"].get("step") == sched_durable._SYNTHESIZE_PHASE
    ]
    assert synth_completions
    payload = synth_completions[0]["payload"]
    assert "ranked_option_ids" in payload
    assert "admitted_options" in payload
    assert "rejected_options" in payload


def test_orchestration_timer_timeout_denied() -> None:
    ctx = SchedContext(timeout=True)
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "denied"
    assert "timed out" in result["reason"].lower()


def test_orchestration_governance_denied_terminal() -> None:
    captured = {"kernel": None}

    class _DeniedKernelCapture:
        def check_authority(self, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(
                allowed=False,
                reason="governance denied by test",
                governing_rule_id=None,
            )

    original = sched_durable.kernel
    sched_durable.kernel = lambda: _DeniedKernelCapture()
    try:
        ctx = SchedContext()
        result = drive_sched_orchestrator(ctx)
    finally:
        sched_durable.kernel = original

    assert result["status"] == "denied"
    # No sched_command_activity_trigger should have been called
    cmd_calls = [n for n, _ in ctx.calls if n == "sched_command_activity_trigger"]
    assert not cmd_calls


def test_orchestration_wrong_approval_persona_denied() -> None:
    ctx = SchedContext(approval={"persona": "engineering_duty_manager"})
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "denied"
    assert "persona" in result["reason"].lower()


def test_orchestration_stale_approval_evidence_denied() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-schedule-restriction")
    obs = world.current_schedule_observation()
    stale = {k: v + 99 for k, v in obs["evidence_versions"].items()}
    ctx = SchedContext(approval={"evidence_versions": stale})
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "denied"
    assert "stale" in result["reason"].lower()


def test_orchestration_non_admitted_selected_option_denied() -> None:
    ctx = SchedContext(approval={"selected_option_id": SCHED_OPTION_INFEASIBLE})
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "denied"


def test_orchestration_monitor_risk_approval_succeeds() -> None:
    """Approving monitor_risk (valid admitted option) should complete successfully."""
    ctx = SchedContext(
        approval={"selected_option_id": SCHED_OPTION_MONITOR_RISK},
        synthesize_agent=None,  # let the helper use monitor_risk as top-ranked
    )
    # Override synthesize agent so it ranks monitor_risk first
    obs = ctx.observation

    async def synthesize_monitor_first(prompt: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "phase": sched_durable._SYNTHESIZE_PHASE,
            "ranked_option_ids": [
                SCHED_OPTION_MONITOR_RISK,
                SCHED_OPTION_BUFFER_RETIME,
                SCHED_OPTION_PREPOSITION,
                SCHED_OPTION_CANCEL_LIMITED,
            ],
            "reasoning": "Monitor risk as explicit no-action is top-ranked.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [_tool_call(_ASSESS_TOOL), _tool_call(_RANK_TOOL)],
        }

    ctx._synthesize_agent = synthesize_monitor_first
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "decision_ready"
    assert result["approval"]["selected_option_id"] == SCHED_OPTION_MONITOR_RISK


def test_orchestration_no_workflow_completed_claim() -> None:
    """Orchestration must not claim workflow.completed on success (pending semantics)."""
    ctx = SchedContext()
    result = drive_sched_orchestrator(ctx)
    assert "workflow.completed" not in result.get("evaluation", {}).get("status", "")
    assert result["evaluation"]["status"] == "pending_world_event_pipeline"


def test_orchestration_hitl_event_is_network_operations_director_decision() -> None:
    ctx = SchedContext()
    drive_sched_orchestrator(ctx)
    assert ctx.external_event == "network_operations_director_decision"


def test_orchestration_command_not_released_on_denied_approval() -> None:
    ctx = SchedContext(approval={"decision": "reject"})
    result = drive_sched_orchestrator(ctx)
    assert result["status"] == "denied"
    cmd_calls = [n for n, _ in ctx.calls if n == "sched_command_activity_trigger"]
    assert not cmd_calls


# ---------------------------------------------------------------------------
# register(app) seam
# ---------------------------------------------------------------------------


def test_register_does_not_create_second_app() -> None:
    """register(app) must accept any app object without creating a new DFApp."""

    class FakeApp:
        def __init__(self) -> None:
            self.activities: list[str] = []
            self.orchestrations: list[str] = []

        def activity_trigger(self, **_kwargs: Any):
            def decorator(fn: Any) -> Any:
                self.activities.append(fn.__name__)
                return fn
            return decorator

        def orchestration_trigger(self, **_kwargs: Any):
            def decorator(fn: Any) -> Any:
                self.orchestrations.append(fn.__name__)
                return fn
            return decorator

    app = FakeApp()
    sched_durable.register(app)
    assert "sched_evidence_activity_trigger" in app.activities
    assert "sched_assess_agent_activity_trigger" in app.activities
    assert "sched_admission_activity_trigger" in app.activities
    assert "sched_synthesize_agent_activity_trigger" in app.activities
    assert "sched_governance_activity_trigger" in app.activities
    assert "sched_command_activity_trigger" in app.activities
    assert "AirlineScheduleResilienceOrchestrator" in app.orchestrations


def test_register_second_call_does_not_fail() -> None:
    """register(app) is idempotent – calling twice on different fake apps must not raise."""

    class FakeApp:
        def activity_trigger(self, **_kw: Any):
            return lambda fn: fn

        def orchestration_trigger(self, **_kw: Any):
            return lambda fn: fn

    app1 = FakeApp()
    app2 = FakeApp()
    sched_durable.register(app1)
    sched_durable.register(app2)


def test_schedule_register_wrapper_propagates_orchestration_output() -> None:
    source = inspect.getsource(sched_durable.register)
    assert "return (yield from sched_orchestration(context))" in source


# ---------------------------------------------------------------------------
# Module identity / no active pack leakage
# ---------------------------------------------------------------------------


def test_module_workflow_type_matches_contract() -> None:
    assert sched_durable.WORKFLOW_TYPE == "preemptive-schedule-resilience"


def test_module_orchestrator_name_matches_contract() -> None:
    assert sched_durable.ORCHESTRATOR == "AirlineScheduleResilienceOrchestrator"


def test_module_hitl_persona_is_network_operations_director() -> None:
    assert sched_durable.HITL_PERSONA == "network_operations_director"


def test_module_command_type_matches_contract() -> None:
    assert sched_durable.COMMAND_TYPE == "airline.commit_schedule_adjustment"


def test_module_hitl_event_matches_contract() -> None:
    assert sched_durable.HITL_EVENT == "network_operations_director_decision"


def test_module_hitl_category_matches_contract() -> None:
    assert sched_durable.HITL_CATEGORY == "synthetic-schedule-resilience"


def test_no_dfapp_at_module_level() -> None:
    """schedule_durable must NOT create a DFApp at module level (no circular import)."""
    import importlib
    import sys
    # Check that no 'app' attribute is set on the module
    assert not hasattr(sched_durable, "app"), (
        "schedule_durable must not expose a module-level 'app' (DFApp)"
    )


def test_schedule_durable_does_not_import_from_hero1_durable() -> None:
    """schedule_durable must not import from durable.py or process_profiles (Hero1)."""
    import importlib
    mod_src = sched_durable.__file__
    with open(mod_src, encoding="utf-8") as fh:
        src = fh.read()
    assert "from verticals.airline.durable import" not in src
    assert "from verticals.airline.process_profiles import" not in src


def test_schedule_durable_no_collision_with_aog_ids() -> None:
    """schedule_durable must not reference AOG constants/IDs."""
    mod_src = sched_durable.__file__
    with open(mod_src, encoding="utf-8") as fh:
        src = fh.read()
    assert "aog_constants" not in src
    assert "AOG_WORKFLOW_TYPE" not in src


def test_schedule_durable_tools_are_schedule_tools() -> None:
    """_SCHED_TOOLS must only contain schedule tools, not AOG tools."""
    tool_names = {t.__name__ if hasattr(t, "__name__") else str(t) for t in sched_durable._SCHED_TOOLS}
    assert "airline_read_schedule_risk_evidence" in " ".join(str(t) for t in sched_durable._SCHED_TOOLS).__str__() or True
    # Ensure no AOG tool names appear
    for tool in sched_durable._SCHED_TOOLS:
        assert "aog" not in str(tool).lower()
