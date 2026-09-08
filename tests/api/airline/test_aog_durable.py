"""TDD tests for Airline Hero 2 – AOG Engineering Recovery Durable core.

Tests cover the six isolated phases:
  1. Detect AOG Event (deterministic evidence)
  2. Check Airworthiness Constraints (deterministic admission)
  3. Synthesize Engineering Recovery Options (agent)
  4. Approve Engineering Recovery (HITL)
  5. Commit Engineering and Operational Actions (deterministic command)
  6. Verify Recovery State (deterministic pending-pipeline)
"""
from __future__ import annotations

import asyncio
import copy
import inspect
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

import verticals.airline.aog_durable as aog_durable
from api.server.services.governance.kernel import _reset_for_tests
from api.shared.vertical_loader import active_runtime
from verticals.airline.aog_constants import (
    AOG_STORY_ID,
    AOG_WORKFLOW_ID,
    AOG_WORKFLOW_TYPE,
)
from verticals.airline.aog_constraints import (
    AOG_OPTION_SUBSTITUTE as _AOG_OPT_SUBSTITUTE,
    AOG_OPTION_WORK_LOCAL as _AOG_OPT_WORK_LOCAL,
    AOG_OPTION_WORK_REPO as _AOG_OPT_WORK_REPO,
    AOG_OPTION_UNAPPROVED as _AOG_OPT_UNAPPROVED,
)
from verticals.airline.mcp_tools.aog import TOOL_NAMES as AOG_TOOL_NAMES
from verticals.airline.worlds.active import (
    register_active_airline_world,
    unregister_active_airline_world,
)
from verticals.airline.worlds.scenario import AirlineWorld

_REAL_KERNEL = aog_durable.kernel

_AOG_ADMITTED_IDS = [
    _AOG_OPT_WORK_LOCAL,
    _AOG_OPT_WORK_REPO,
    _AOG_OPT_SUBSTITUTE,
]

_DEFAULT_SELECTED = _AOG_OPT_WORK_LOCAL
_DEFAULT_DECISION_ID = "SYN-AOG-DECISION-001"


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


def _valid_aog_agent(context: AogContext, captured: list[dict[str, Any]] | None = None):
    async def fake(prompt: str, **kwargs: Any) -> dict[str, Any]:
        if captured is not None:
            captured.append({"prompt": prompt, **kwargs})
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "All admitted AOG options evaluated; work-local preferred.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    return fake


class AogContext:
    instance_id = "aog-instance-1"
    current_utc_datetime = datetime(2026, 8, 11)

    def __init__(
        self,
        *,
        approval: dict[str, Any] | None = None,
        timeout: bool = False,
    ) -> None:
        self.world = AirlineWorld(seed=42)
        self.world.install()
        self.world.activate_scenario("synthetic-aog-defect")
        self.observation = self.world.current_aog_observation()
        # Ensure actor_ids and event_ids present on observation for agent fake
        self.observation["actor_ids"] = sorted(self.observation["evidence_versions"])
        self.observation["event_ids"] = list(self.observation["evidence_event_ids"])

        self._input = {
            "workflow_id": AOG_WORKFLOW_ID,
            "type": AOG_WORKFLOW_TYPE,
        }
        base = {
            "decision": "approve",
            "persona": "engineering_duty_manager",
            "decision_id": _DEFAULT_DECISION_ID,
            "selected_option_id": _DEFAULT_SELECTED,
            "evidence_versions": copy.deepcopy(self.observation["evidence_versions"]),
            "workflow_id": AOG_WORKFLOW_ID,
            "story_id": AOG_STORY_ID,
        }
        if approval is not None:
            base.update(approval)
        self._approval_data = base
        self.approval = _Task(base)
        self.timer = _Task()
        self.timeout = timeout
        self.external_event: str | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_input(self) -> dict[str, Any]:
        return self._input

    def call_activity(self, name: str, payload: dict[str, Any]) -> Any:
        self.calls.append((name, payload))
        if name == "aog_evidence_activity_trigger":
            return aog_durable.aog_evidence_activity(payload, world=self.world)
        if name == "aog_airworthiness_activity_trigger":
            return aog_durable.aog_airworthiness_activity(payload)
        if name == "aog_agent_activity_trigger":
            return aog_durable.aog_agent_activity(payload)
        if name == "aog_governance_activity_trigger":
            return aog_durable.aog_governance_activity(payload)
        if name == "aog_command_activity_trigger":
            return aog_durable.aog_command_activity(payload, world=self.world)
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
            governing_rule_id="AOG-TEST-001",
        )


@pytest.fixture(autouse=True)
def _allow_aog_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aog_durable, "kernel", lambda: _AllowedKernel())


@pytest.fixture
def _use_real_aog_kernel(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ZAVA_VERTICAL", "airline")
    monkeypatch.delenv("ZAVA_WORLD", raising=False)
    active_runtime.cache_clear()
    _reset_for_tests()
    monkeypatch.setattr(aog_durable, "kernel", _REAL_KERNEL)
    try:
        yield
    finally:
        _reset_for_tests()
        active_runtime.cache_clear()


def drive_aog_orchestrator(context: AogContext) -> dict[str, Any]:
    generator = aog_durable.aog_orchestration(context)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


def test_aog_agent_prompt_requires_non_empty_reasoning() -> None:
    context = AogContext()
    evidence = aog_durable.aog_evidence_activity(
        context.get_input(),
        world=context.world,
    )
    admission = aog_durable.aog_airworthiness_activity({"evidence": evidence})
    prompt = aog_durable._aog_agent_prompt(
        {
            **context.get_input(),
            "instance_id": context.instance_id,
            "evidence": evidence,
            "admitted_options": admission["admitted_options"],
        }
    )

    assert "reasoning MUST be a non-empty string" in prompt
    assert "Call each required tool at least once" in prompt


def _step_checkpoints(context: AogContext) -> list[tuple[str, str]]:
    return [
        (payload["kind"], payload["payload"]["step"])
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
        and payload["kind"] in {"step.started", "step.completed"}
    ]


def _terminal_checkpoints(context: AogContext) -> list[dict[str, Any]]:
    return [
        {"kind": payload["kind"], **payload["payload"]}
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger" and payload["kind"] == "workflow.completed"
    ]


def _suspended_checkpoint(context: AogContext) -> dict[str, Any] | None:
    for name, payload in context.calls:
        if name == "checkpoint_activity_trigger" and payload["kind"] == "suspended":
            return payload["payload"]
    return None


def _command_calls(context: AogContext) -> list[dict[str, Any]]:
    return [payload for name, payload in context.calls if name == "aog_command_activity_trigger"]


def _assert_terminal_denial(context: AogContext, result: dict[str, Any]) -> None:
    assert _terminal_checkpoints(context) == [
        {
            "kind": "workflow.completed",
            "status": result["status"],
            "reason": result["reason"],
            "workflow_type": AOG_WORKFLOW_TYPE,
        }
    ]


# ===========================================================================
# 1. Evidence activity
# ===========================================================================


def test_aog_evidence_activity_returns_observation_from_world() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")

    result = aog_durable.aog_evidence_activity(
        {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
        world=world,
    )

    assert result["workflow_id"] == AOG_WORKFLOW_ID
    assert result["story_id"] == AOG_STORY_ID


def test_aog_evidence_activity_uses_bridge_observation_and_arms_worker_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = AirlineWorld(seed=42)
    source.install()
    source.activate_scenario("synthetic-aog-defect")
    observation = source.current_aog_observation()
    observation["trace_id"] = "bridge-aog-trace"
    worker = AirlineWorld(seed=42)
    worker.install()
    monkeypatch.setattr(aog_durable, "_active_world", lambda: worker)

    result = aog_durable.aog_evidence_activity(
        {
            "workflow_id": "AOGA-0001",
            "type": AOG_WORKFLOW_TYPE,
            "observation": observation,
        }
    )

    assert result["observation"]["sensor_event_id"] == observation["sensor_event_id"]
    assert worker.aog_story_status[AOG_STORY_ID] == "active"
    assert worker.current_aog_observation()["trace_id"] == "bridge-aog-trace"
    assert result["source_mode"] == "simulated"
    assert isinstance(result["observation"], dict)
    assert isinstance(result["evidence_versions"], dict)
    assert result["evidence_versions"]
    assert isinstance(result["actor_ids"], list)
    assert result["actor_ids"]
    assert isinstance(result["event_ids"], list)
    assert result["event_ids"]


def test_aog_diagnostic_resets_worker_shadow_world(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from verticals.airline.lifecycle import (
        ensure_airline_worker_world,
        shutdown_airline_worker_world,
    )

    monkeypatch.setenv("FUNCTIONS_WORKER_RUNTIME", "python")
    shutdown_airline_worker_world()
    worker = ensure_airline_worker_world()
    worker.aircraft["SYN-TAIL-005"].version += 1

    source = AirlineWorld(seed=42)
    source.install()
    source.activate_scenario("synthetic-aog-defect")
    observation = source.current_aog_observation()
    try:
        aog_durable.aog_evidence_activity({
            "workflow_id": AOG_WORKFLOW_ID,
            "type": AOG_WORKFLOW_TYPE,
            "observation": observation,
            "diagnostic": True,
        })
        reset_worker = aog_durable._active_world()
        assert reset_worker is not worker
        assert (
            reset_worker.current_aog_observation()["evidence_versions"]
            == observation["evidence_versions"]
        )
    finally:
        shutdown_airline_worker_world()


def test_aog_evidence_activity_wrong_workflow_type_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")

    with pytest.raises(ValueError, match="workflow type"):
        aog_durable.aog_evidence_activity(
            {"workflow_id": AOG_WORKFLOW_ID, "type": "wrong-type"},
            world=world,
        )


def test_aog_evidence_activity_missing_workflow_id_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")

    with pytest.raises(ValueError):
        aog_durable.aog_evidence_activity(
            {"type": AOG_WORKFLOW_TYPE},
            world=world,
        )


def test_aog_evidence_activity_no_active_world_raises() -> None:
    """Fails closed when no world is available."""
    with pytest.raises((ValueError, RuntimeError)):
        aog_durable.aog_evidence_activity(
            {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
            world=None,
        )


def test_aog_evidence_activity_inactive_aog_story_raises() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    # AOG scenario NOT activated

    with pytest.raises((ValueError, RuntimeError)):
        aog_durable.aog_evidence_activity(
            {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
            world=world,
        )


# ===========================================================================
# 2. Airworthiness / admission activity
# ===========================================================================


def test_aog_airworthiness_activity_returns_admitted_and_rejected() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    evidence = aog_durable.aog_evidence_activity(
        {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
        world=world,
    )

    result = aog_durable.aog_airworthiness_activity({"evidence": evidence})

    assert isinstance(result["admitted_options"], list)
    assert result["admitted_options"]
    admitted_ids = {opt["option_id"] for opt in result["admitted_options"]}
    assert _AOG_OPT_WORK_LOCAL in admitted_ids
    assert _AOG_OPT_WORK_REPO in admitted_ids
    assert _AOG_OPT_SUBSTITUTE in admitted_ids
    assert isinstance(result["rejected_options"], list)
    assert any(opt["option_id"] == _AOG_OPT_UNAPPROVED for opt in result["rejected_options"])


def test_aog_airworthiness_activity_admitted_options_have_required_fields() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    evidence = aog_durable.aog_evidence_activity(
        {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
        world=world,
    )

    result = aog_durable.aog_airworthiness_activity({"evidence": evidence})

    for opt in result["admitted_options"]:
        assert opt["feasible"] is True
        assert opt["admitted"] is True
        assert isinstance(opt["actions"], list)
        assert opt["actions"]
        assert isinstance(opt["evidence_versions"], dict)
        assert opt["evidence_versions"]
        assert isinstance(opt["value_gbp"], float)


def test_aog_airworthiness_activity_never_alters_feasibility() -> None:
    """The admission activity must not change feasibility of any option."""
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    evidence = aog_durable.aog_evidence_activity(
        {"workflow_id": AOG_WORKFLOW_ID, "type": AOG_WORKFLOW_TYPE},
        world=world,
    )
    original_obs = copy.deepcopy(evidence["observation"])

    result = aog_durable.aog_airworthiness_activity({"evidence": evidence})

    # Calling admission again on the same evidence should yield same results
    result2 = aog_durable.aog_airworthiness_activity({"evidence": evidence})
    assert [o["option_id"] for o in result["admitted_options"]] == [
        o["option_id"] for o in result2["admitted_options"]
    ]
    assert [o["option_id"] for o in result["rejected_options"]] == [
        o["option_id"] for o in result2["rejected_options"]
    ]
    # observation must not be mutated
    assert evidence["observation"] == original_obs


def test_aog_airworthiness_activity_missing_evidence_raises() -> None:
    with pytest.raises(ValueError):
        aog_durable.aog_airworthiness_activity({})


# ===========================================================================
# 3. Agent activity
# ===========================================================================


def _make_agent_payload(context: AogContext) -> dict[str, Any]:
    evidence = aog_durable.aog_evidence_activity(
        context.get_input(),
        world=context.world,
    )
    admission = aog_durable.aog_airworthiness_activity({"evidence": evidence})
    return {
        **context.get_input(),
        "instance_id": context.instance_id,
        "phase": aog_durable._AGENT_PHASE,
        "evidence": evidence,
        "admitted_options": admission["admitted_options"],
    }


def test_aog_agent_activity_requires_both_tool_types(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_one_tool(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Only one tool called.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [_tool_call("airline_read_aog_evidence")],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_one_tool)

    with pytest.raises(ValueError, match="missing"):
        aog_durable.aog_agent_activity(payload)


def test_aog_agent_activity_retry_on_no_tool_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)
    call_count = {"n": 0}

    async def fake_retry(prompt: str, **kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        obs = context.observation
        if call_count["n"] == 1:
            return {
                "phase": aog_durable._AGENT_PHASE,
                "ranked_option_ids": list(_AOG_ADMITTED_IDS),
                "reasoning": "First attempt no tools.",
                "evidence_versions": obs["evidence_versions"],
                "actor_ids": obs["actor_ids"],
                "event_ids": obs["event_ids"],
            }
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Retry succeeded.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_retry)

    result = aog_durable.aog_agent_activity(payload)

    assert call_count["n"] == 2
    assert result["ranked_option_ids"] == list(_AOG_ADMITTED_IDS)


def test_aog_agent_activity_retries_failed_declared_tool_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)
    call_count = {"n": 0}

    async def fake_retry(prompt: str, **kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Retry succeeded.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call(
                    "airline_read_aog_evidence",
                    success=call_count["n"] > 1,
                ),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_retry)

    result = aog_durable.aog_agent_activity(payload)

    assert call_count["n"] == 2
    assert result["ranked_option_ids"] == list(_AOG_ADMITTED_IDS)


def test_aog_agent_activity_no_retry_on_malformed_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)
    call_count = {"n": 0}

    async def fake_malformed(prompt: str, **kwargs: Any) -> dict[str, Any]:
        call_count["n"] += 1
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Malformed tool evidence.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                {"bad": "structure"},
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_malformed)

    with pytest.raises(ValueError):
        aog_durable.aog_agent_activity(payload)

    assert call_count["n"] == 1


def test_aog_agent_activity_fails_on_unknown_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_unknown(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Used unknown tool.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_unknown_tool"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_unknown)

    with pytest.raises(ValueError, match="undeclared"):
        aog_durable.aog_agent_activity(payload)


def test_aog_agent_activity_fails_when_required_rank_tool_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_duplicate(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Duplicate tool call.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_read_aog_evidence"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_duplicate)

    with pytest.raises(ValueError):
        aog_durable.aog_agent_activity(payload)


def test_aog_agent_activity_preserves_successful_duplicate_read_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_duplicate(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Both required tools succeeded; one read was repeated.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_duplicate)

    result = aog_durable.aog_agent_activity(payload)

    assert result["ranked_option_ids"] == list(_AOG_ADMITTED_IDS)


def test_aog_agent_activity_accepts_failed_read_followed_by_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_self_corrected(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "The agent corrected its read arguments before ranking.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence", success=False),
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_self_corrected)

    result = aog_durable.aog_agent_activity(payload)

    assert result["ranked_option_ids"] == list(_AOG_ADMITTED_IDS)


def test_aog_agent_activity_fails_on_failed_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_failed(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Tool call failed.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence", success=False),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_failed)

    with pytest.raises(ValueError, match="unsuccessful"):
        aog_durable.aog_agent_activity(payload)


def test_aog_agent_activity_passes_correct_skill_and_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)
    captured: list[dict[str, Any]] = []

    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context, captured))

    aog_durable.aog_agent_activity(payload)

    assert len(captured) >= 1
    call = captured[0]
    assert call["phase"] == aog_durable._AGENT_PHASE
    assert call["workflow_id"] == AOG_WORKFLOW_ID
    assert call["instance_id"] == context.instance_id
    # skill dir must be the aog-recovery-ranker
    from pathlib import Path
    assert Path(call["skill_dir"]).name == "aog-recovery-ranker"
    # tools must be both AOG tools
    tool_names = {t.name for t in call["tools"]}
    assert tool_names == AOG_TOOL_NAMES


def test_aog_agent_activity_fails_on_wrong_ranked_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_wrong_ids(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": ["WRONG-ID"],
            "reasoning": "Wrong IDs.",
            "evidence_versions": obs["evidence_versions"],
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_wrong_ids)

    with pytest.raises(ValueError, match="ranking"):
        aog_durable.aog_agent_activity(payload)


def test_aog_agent_activity_fails_on_changed_evidence_versions(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    payload = _make_agent_payload(context)

    async def fake_changed_versions(prompt: str, **kwargs: Any) -> dict[str, Any]:
        obs = context.observation
        return {
            "phase": aog_durable._AGENT_PHASE,
            "ranked_option_ids": list(_AOG_ADMITTED_IDS),
            "reasoning": "Changed evidence versions.",
            "evidence_versions": {"WRONG-ID": 99},
            "actor_ids": obs["actor_ids"],
            "event_ids": obs["event_ids"],
            "_raw_tool_calls": [
                _tool_call("airline_read_aog_evidence"),
                _tool_call("airline_rank_admitted_aog_options"),
            ],
        }

    monkeypatch.setattr(aog_durable, "run_agent_session", fake_changed_versions)

    with pytest.raises(ValueError, match="evidence versions"):
        aog_durable.aog_agent_activity(payload)


# ===========================================================================
# 4. Governance activity
# ===========================================================================


def test_aog_governance_activity_allows_within_limit(_use_real_aog_kernel) -> None:
    result = aog_durable.aog_governance_activity(
        {"selected_option": {"value_gbp": 85_000.0}}
    )
    assert result["allowed"] is True
    assert isinstance(result["reason"], str)
    assert isinstance(result["governing_rule_id"], str)


def test_aog_governance_activity_denies_over_limit(_use_real_aog_kernel) -> None:
    result = aog_durable.aog_governance_activity(
        {"selected_option": {"value_gbp": 250_000.0}}
    )
    assert result["allowed"] is False
    assert result["reason"]


def test_aog_governance_activity_non_finite_value_raises() -> None:
    import math
    with pytest.raises(ValueError, match="finite"):
        aog_durable.aog_governance_activity(
            {"selected_option": {"value_gbp": math.inf}}
        )


# ===========================================================================
# 5. Orchestration – phase/checkpoint order
# ===========================================================================


def test_aog_checkpoint_phase_order(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(timeout=True)
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    drive_aog_orchestrator(context)

    assert _step_checkpoints(context) == [
        ("step.started", "Detect AOG Event"),
        ("step.completed", "Detect AOG Event"),
        ("step.started", "Check Airworthiness Constraints"),
        ("step.completed", "Check Airworthiness Constraints"),
        ("step.started", "Synthesize Engineering Recovery Options"),
        ("step.completed", "Synthesize Engineering Recovery Options"),
    ]


def test_aog_orchestrator_emits_workflow_started_first(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(timeout=True)
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    drive_aog_orchestrator(context)

    kinds = [payload["kind"] for name, payload in context.calls if name == "checkpoint_activity_trigger"]
    assert kinds[0] == "workflow.started"


# ===========================================================================
# 6. Orchestration – golden path (decision_ready)
# ===========================================================================


def test_aog_orchestrator_golden_path_returns_decision_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "decision_ready"
    assert result["workflow_id"] == "AOGA-0001"
    assert result["command"]["type"] == "airline.commit_aog_recovery"
    assert result["command"]["payload"]["option_id"] == _DEFAULT_SELECTED
    assert _terminal_checkpoints(context) == []


def test_aog_orchestrator_uses_exact_hitl_event(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(timeout=True)
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    drive_aog_orchestrator(context)

    assert context.external_event == "engineering_duty_manager_decision"


def test_aog_orchestrator_golden_path_step_order_includes_commit_and_verify(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    drive_aog_orchestrator(context)

    steps = _step_checkpoints(context)
    assert ("step.started", "Commit Engineering and Operational Actions") in steps
    assert ("step.completed", "Commit Engineering and Operational Actions") in steps
    assert ("step.completed", "Verify Recovery State") in steps
    # Verify recovery state has pending_world_event_pipeline status
    verify_payload = next(
        payload["payload"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
        and payload["kind"] == "step.completed"
        and payload["payload"].get("step") == "Verify Recovery State"
    )
    assert verify_payload["status"] == "pending_world_event_pipeline"


def test_aog_orchestrator_golden_path_evaluation_is_pending_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["evaluation"]["status"] == "pending_world_event_pipeline"
    assert result["evaluation"]["success_event"] == "airline.aog_recovery.applied"


def test_aog_orchestrator_no_aircraft_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aircraft must remain grounded after command; AI must not release it."""
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))
    from verticals.airline.aog_constants import AOG_AFFECTED_TAIL_ID

    drive_aog_orchestrator(context)

    aircraft = context.world.aircraft[AOG_AFFECTED_TAIL_ID]
    assert aircraft.status in {"grounded", "work_in_progress"}
    # Check evaluation explicitly
    for _, evaluation in context.world.aog_recovery_evaluations.items():
        assert evaluation.aircraft_released_by_ai is False


# ===========================================================================
# 7. HITL context completeness
# ===========================================================================


def test_aog_suspended_checkpoint_persists_complete_hitl_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext(timeout=True)
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    drive_aog_orchestrator(context)

    suspended = _suspended_checkpoint(context)
    assert suspended is not None
    assert suspended["persona"] == "engineering_duty_manager"
    assert suspended["external_event"] == "engineering_duty_manager_decision"
    assert suspended["phase"] == "Approve Engineering Recovery"

    hitl = suspended["hitl_context"]
    assert suspended["context"] == hitl

    required_keys = {
        "workflow_id", "instance_id", "workflow_type", "story_id",
        "persona", "external_event", "phase", "action",
        "request", "observation", "evidence", "admitted_options",
        "rejected_options", "ranking", "selected_option", "selected_option_id",
        "decision_id", "evidence_versions", "authority",
    }
    for key in required_keys:
        assert key in hitl, f"hitl_context missing: {key}"

    assert hitl["workflow_id"] == AOG_WORKFLOW_ID
    assert hitl["workflow_type"] == AOG_WORKFLOW_TYPE
    assert hitl["story_id"] == AOG_STORY_ID
    assert hitl["persona"] == "engineering_duty_manager"
    assert hitl["external_event"] == "engineering_duty_manager_decision"
    assert hitl["phase"] == "Approve Engineering Recovery"
    assert hitl["action"] == "airline.commit_aog_recovery"
    assert hitl["request"]["category"] == "synthetic-engineering-recovery"
    assert hitl["request"]["amount_gbp"] > 0
    assert hitl["evidence_versions"]
    assert hitl["admitted_options"]
    assert hitl["rejected_options"]
    assert isinstance(hitl["ranking"]["ranked_option_ids"], list)


# ===========================================================================
# 8. HITL rejection scenarios
# ===========================================================================


def test_aog_orchestrator_timeout_returns_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(timeout=True)
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "timed out" in result["reason"]
    assert result["command"] is None
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_reject_decision_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"decision": "reject", "persona": "engineering_duty_manager"}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "approve" in result["reason"]
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_wrong_persona_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"decision": "approve", "persona": "duty_operations_manager"}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "persona" in result["reason"]
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_stale_evidence_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"evidence_versions": {"WRONG-ID": 1}}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "stale" in result["reason"]
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_rejected_option_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"selected_option_id": _AOG_OPT_UNAPPROVED}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "option" in result["reason"]
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_non_admitted_option_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"selected_option_id": "COMPLETELY-UNKNOWN-OPTION"}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "option" in result["reason"]
    assert not _command_calls(context)
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_wrong_story_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"story_id": "SYN-STORY-WRONG"}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "story" in result["reason"]
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_option_not_matching_ranking_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selected option must match the governed top ranking (first in ranked_option_ids)."""
    context = AogContext(
        approval={"selected_option_id": _AOG_OPT_SUBSTITUTE}  # not top of ranking
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "governed" in result["reason"] or "ranking" in result["reason"]
    _assert_terminal_denial(context, result)


def test_aog_orchestrator_missing_decision_id_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    context = AogContext(
        approval={"decision_id": ""}
    )
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert "decision_id" in result["reason"]
    _assert_terminal_denial(context, result)


# ===========================================================================
# 9. Governance denial terminal
# ===========================================================================


def test_aog_orchestrator_governance_denial_returns_terminal(
    monkeypatch: pytest.MonkeyPatch,
    _use_real_aog_kernel,
) -> None:
    """If governance denies, orchestration emits terminal checkpoint and stops."""
    context = AogContext()
    # Override observation to have a high-value option
    # We'll force a very large value in the ranking; fake agent returns work-local (85k)
    # but override selected option to 250k by monkeypatching governance check via a custom agent

    class _DenyKernel:
        def check_authority(self, **_kw: Any) -> SimpleNamespace:
            return SimpleNamespace(allowed=False, reason="spend limit exceeded", governing_rule_id="AOG-DENY")

    monkeypatch.setattr(aog_durable, "kernel", lambda: _DenyKernel())
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "denied"
    assert result["reason"]
    _assert_terminal_denial(context, result)
    assert not _command_calls(context)


# ===========================================================================
# 10. Command activity
# ===========================================================================


def test_aog_command_activity_creates_work_order() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    obs = world.current_aog_observation()
    evidence_versions = obs["evidence_versions"]

    result = aog_durable.aog_command_activity(
        {
            "workflow_id": AOG_WORKFLOW_ID,
            "approval": {
                "selected_option_id": _AOG_OPT_WORK_LOCAL,
                "decision_id": _DEFAULT_DECISION_ID,
            },
            "hitl_context": {"evidence_versions": evidence_versions},
        },
        world=world,
    )

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == "airline.commit_aog_recovery"
    assert world.engineering_work_orders
    assert world.spare_movements


def test_aog_command_activity_idempotent_retry() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    obs = world.current_aog_observation()
    evidence_versions = obs["evidence_versions"]
    payload = {
        "workflow_id": AOG_WORKFLOW_ID,
        "approval": {
            "selected_option_id": _AOG_OPT_WORK_LOCAL,
            "decision_id": _DEFAULT_DECISION_ID,
        },
        "hitl_context": {"evidence_versions": evidence_versions},
    }

    result1 = aog_durable.aog_command_activity(payload, world=world)
    result2 = aog_durable.aog_command_activity(payload, world=world)

    assert result1["status"] == "decision_ready"
    assert result2["status"] == "decision_ready"
    assert result1["command"]["command_id"] == result2["command"]["command_id"]


def test_aog_command_activity_stale_world_denied() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    obs = world.current_aog_observation()
    stale_versions = {k: v + 99 for k, v in obs["evidence_versions"].items()}

    result = aog_durable.aog_command_activity(
        {
            "workflow_id": AOG_WORKFLOW_ID,
            "approval": {
                "selected_option_id": _AOG_OPT_WORK_LOCAL,
                "decision_id": _DEFAULT_DECISION_ID,
            },
            "hitl_context": {"evidence_versions": stale_versions},
        },
        world=world,
    )

    assert result["status"] == "denied"
    assert "stale" in result["reason"]


def test_aog_command_activity_inactive_aog_story_denied() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    obs = world.current_aog_observation()
    evidence_versions = obs["evidence_versions"]
    # Deactivate the story
    world.aog_story_status[AOG_STORY_ID] = "resolved"

    result = aog_durable.aog_command_activity(
        {
            "workflow_id": AOG_WORKFLOW_ID,
            "approval": {
                "selected_option_id": _AOG_OPT_WORK_LOCAL,
                "decision_id": _DEFAULT_DECISION_ID,
            },
            "hitl_context": {"evidence_versions": evidence_versions},
        },
        world=world,
    )

    assert result["status"] == "denied"


def test_aog_command_activity_no_aircraft_release() -> None:
    world = AirlineWorld(seed=42)
    world.install()
    world.activate_scenario("synthetic-aog-defect")
    obs = world.current_aog_observation()
    evidence_versions = obs["evidence_versions"]
    from verticals.airline.aog_constants import AOG_AFFECTED_TAIL_ID

    aog_durable.aog_command_activity(
        {
            "workflow_id": AOG_WORKFLOW_ID,
            "approval": {
                "selected_option_id": _AOG_OPT_WORK_LOCAL,
                "decision_id": _DEFAULT_DECISION_ID,
            },
            "hitl_context": {"evidence_versions": evidence_versions},
        },
        world=world,
    )

    aircraft = world.aircraft[AOG_AFFECTED_TAIL_ID]
    assert aircraft.status not in {"operational", "serviceable"}
    for _, ev in world.aog_recovery_evaluations.items():
        assert ev.aircraft_released_by_ai is False


# ===========================================================================
# 11. Pending-world terminal semantics
# ===========================================================================


def test_aog_orchestrator_decision_ready_no_false_terminal_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    # decision_ready result must NOT have a workflow.completed terminal checkpoint
    assert result["status"] == "decision_ready"
    assert _terminal_checkpoints(context) == []


def test_aog_orchestrator_decision_ready_does_not_claim_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = AogContext()
    monkeypatch.setattr(aog_durable, "run_agent_session", _valid_aog_agent(context))

    result = drive_aog_orchestrator(context)

    assert result["status"] == "decision_ready"
    assert "completed" not in result.get("status", "")
    assert "success" not in result.get("status", "")


# ===========================================================================
# 12. register(app) structural contract
# ===========================================================================


def test_register_app_registers_named_orchestrator() -> None:
    registered: list[str] = []

    class FakeApp:
        def activity_trigger(self, *, input_name: str):
            def decorator(fn):
                registered.append(f"activity:{fn.__name__}")
                return fn
            return decorator

        def orchestration_trigger(self, *, context_name: str):
            def decorator(fn):
                registered.append(f"orchestration:{fn.__name__}")
                return fn
            return decorator

    fake = FakeApp()
    aog_durable.register(fake)

    assert "orchestration:AirlineAogEngineeringRecoveryOrchestrator" in registered
    assert any(name.startswith("activity:aog_evidence") for name in registered)
    assert any(name.startswith("activity:aog_airworthiness") for name in registered)
    assert any(name.startswith("activity:aog_agent") for name in registered)
    assert any(name.startswith("activity:aog_governance") for name in registered)
    assert any(name.startswith("activity:aog_command") for name in registered)


def test_aog_register_wrapper_propagates_orchestration_output() -> None:
    source = inspect.getsource(aog_durable.register)
    assert "return (yield from aog_orchestration(context))" in source


# ===========================================================================
# 13. Module constants / contract
# ===========================================================================


def test_aog_module_constants_match_contract() -> None:
    assert aog_durable.WORKFLOW_TYPE == "aog-engineering-recovery"
    assert aog_durable.ORCHESTRATOR == "AirlineAogEngineeringRecoveryOrchestrator"
    assert aog_durable._DETECT_PHASE == "Detect AOG Event"
    assert aog_durable._AIRWORTHINESS_PHASE == "Check Airworthiness Constraints"
    assert aog_durable._AGENT_PHASE == "Synthesize Engineering Recovery Options"
    assert aog_durable._HITL_PHASE == "Approve Engineering Recovery"
    assert aog_durable._COMMIT_PHASE == "Commit Engineering and Operational Actions"
    assert aog_durable._VERIFY_PHASE == "Verify Recovery State"
    assert aog_durable.HITL_PERSONA == "engineering_duty_manager"
    assert aog_durable.HITL_EVENT == "engineering_duty_manager_decision"
    assert aog_durable.COMMAND_TYPE == "airline.commit_aog_recovery"
    assert aog_durable.HITL_CATEGORY == "synthetic-engineering-recovery"
