from __future__ import annotations

import copy
import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

import verticals.airline.durable as durable
from api.server.world.runtime import SimulationRuntime
from verticals.airline.mcp_tools import operations
from verticals.airline.worlds.scenario import AirlineWorld


class _Task:
    def __init__(self, result: Any = None) -> None:
        self.result = result
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class AirlineContext:
    instance_id = "airline-instance-1"
    current_utc_datetime = datetime(2026, 7, 28)

    def __init__(
        self,
        *,
        approval: dict[str, Any] | None = None,
        timeout: bool = False,
    ) -> None:
        runtime = SimulationRuntime(seed=42)
        self.world = AirlineWorld(seed=42, runtime=runtime)
        self.world.install()
        self.world.activate_scenario("synthetic-hub-cascade")
        sensor = next(
            event
            for event in runtime.journal
            if event.type == "sensor.tripped" and event.actor_id == "sensor:integrated_hub_disruption"
        )
        self.observation = self.world.build_observation(sensor.to_dict())
        self.observation["actor_ids"] = list(self.observation["evidence_versions"])
        self.observation["event_ids"] = list(self.observation["evidence_event_ids"])
        self._input = {
            "workflow_id": "AIRHUB-0001",
            "type": "integrated-hub-disruption-recovery",
            "observation": copy.deepcopy(self.observation),
        }
        supplied_approval = dict(approval or {})
        supplied_approval.setdefault(
            "evidence_versions",
            copy.deepcopy(self.observation["evidence_versions"]),
        )
        supplied_approval.setdefault("workflow_id", "AIRHUB-0001")
        supplied_approval.setdefault("story_id", "SYN-STORY-HUB-001")
        supplied_approval.setdefault("rationale", "Synthetic recovery evidence is current.")
        self.approval = _Task(supplied_approval)
        self.timer = _Task()
        self.timeout = timeout
        self.external_event: str | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_input(self) -> dict[str, Any]:
        return self._input

    def call_activity(self, name: str, payload: dict[str, Any]) -> Any:
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
            return durable.airline_command_activity(payload, world=self.world)
        return {"checkpoint": payload["kind"]}

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
            governing_rule_id="AIRLINE-TEST-001",
        )


@pytest.fixture(autouse=True)
def _allow_airline_authority(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(durable, "kernel", lambda: _AllowedKernel())


def drive_airline_orchestrator(context: AirlineContext) -> dict[str, Any]:
    generator = durable.airline_orchestration(context)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


def _valid_agent(
    context: AirlineContext,
    captured: list[dict[str, Any]] | None = None,
):
    async def fake_run_agent_session(prompt: str, **kwargs: Any) -> dict[str, Any]:
        if captured is not None:
            captured.append({"prompt": prompt, **kwargs})
        phase = kwargs["phase"]
        if phase == "Assess Network Impact":
            return {
                "phase": phase,
                "actor_ids": context.observation["actor_ids"],
                "event_ids": context.observation["event_ids"],
                "impact_summary": "Rotation, crew, stand and connection impact.",
            }
        return {
            "phase": phase,
            "ranked_option_ids": [
                "SYN-OPTION-TAIL-CREW-STAND",
                "SYN-OPTION-CANCEL",
            ],
            "reasoning": "Ranks only admitted options.",
        }

    return fake_run_agent_session


def _command_activity_calls(context: AirlineContext) -> list[dict[str, Any]]:
    return [payload for name, payload in context.calls if name == "airline_command_activity_trigger"]


def test_golden_orchestrator_uses_real_agent_identity_and_exact_hitl_event(
    monkeypatch,
) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        }
    )
    captured = []

    async def fake_run_agent_session(prompt: str, **kwargs):
        captured.append(kwargs)
        phase = kwargs["phase"]
        if phase == "Assess Network Impact":
            return {
                "phase": phase,
                "actor_ids": context.observation["actor_ids"],
                "event_ids": context.observation["event_ids"],
                "impact_summary": "Rotation, crew, stand and connection impact.",
            }
        return {
            "phase": phase,
            "ranked_option_ids": [
                "SYN-OPTION-TAIL-CREW-STAND",
                "SYN-OPTION-CANCEL",
            ],
            "reasoning": "Ranks only admitted options.",
        }

    monkeypatch.setattr(
        "verticals.airline.durable.run_agent_session",
        fake_run_agent_session,
    )
    result = drive_airline_orchestrator(context)
    assert context.external_event == "duty_operations_manager_decision"
    assert [item["phase"] for item in captured] == [
        "Assess Network Impact",
        "Synthesize Recovery Options",
    ]
    assert all(item["workflow_id"] == "AIRHUB-0001" for item in captured)
    assert all(item["instance_id"] == context.instance_id for item in captured)
    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == "airline.commit_recovery_plan"


def test_rejection_decision_returns_denied_without_command(monkeypatch) -> None:
    context = AirlineContext(
        approval={
            "decision": "reject",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        }
    )
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "approve" in result["reason"]
    assert result["command"] is None
    assert not _command_activity_calls(context)


def test_wrong_persona_returns_denied_without_command(monkeypatch) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "network_controller",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        }
    )
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "persona" in result["reason"]
    assert result["command"] is None
    assert not _command_activity_calls(context)


@pytest.mark.parametrize(
    "selected_option_id",
    ["SYN-OPTION-CANCEL", "SYN-OPTION-NOT-ADMITTED"],
)
def test_wrong_or_non_admitted_option_returns_denied(
    monkeypatch,
    selected_option_id: str,
) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": selected_option_id,
        }
    )
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "option" in result["reason"]
    assert result["command"] is None
    assert not _command_activity_calls(context)


def test_stale_approval_evidence_returns_denied_without_command(monkeypatch) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
            "evidence_versions": {"SYN-SECTOR-IN-001": 1},
        }
    )
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "stale" in result["reason"]
    assert result["command"] is None
    assert not _command_activity_calls(context)


def test_world_evidence_changed_after_checkpoint_returns_denied(monkeypatch) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        }
    )
    context.world.sectors["SYN-SECTOR-OUT-001"].version += 1
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "stale" in result["reason"]
    assert result["command"] is None


def test_timeout_returns_denied_without_command(monkeypatch) -> None:
    context = AirlineContext(timeout=True)
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert "timed out" in result["reason"]
    assert result["command"] is None
    assert not _command_activity_calls(context)


def test_suspended_checkpoint_persists_complete_hitl_context(monkeypatch) -> None:
    context = AirlineContext(timeout=True)
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    drive_airline_orchestrator(context)

    suspended = next(
        payload["payload"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger" and payload["kind"] == "suspended"
    )
    assert suspended["persona"] == "duty_operations_manager"
    assert suspended["external_event"] == "duty_operations_manager_decision"
    assert suspended["phase"] == "Approve Recovery Plan"
    hitl_context = suspended["hitl_context"]
    assert hitl_context["workflow_id"] == "AIRHUB-0001"
    assert hitl_context["instance_id"] == context.instance_id
    assert hitl_context["story_id"] == "SYN-STORY-HUB-001"
    assert hitl_context["observation"] == context.observation
    assert hitl_context["evidence"]["evidence_versions"]
    assert hitl_context["impact"]["actor_ids"] == context.observation["actor_ids"]
    assert [item["option_id"] for item in hitl_context["admitted_options"]] == [
        "SYN-OPTION-TAIL-CREW-STAND",
        "SYN-OPTION-CANCEL",
    ]
    assert hitl_context["ranking"]["ranked_option_ids"] == [
        "SYN-OPTION-TAIL-CREW-STAND",
        "SYN-OPTION-CANCEL",
    ]
    assert hitl_context["selected_option"]["option_id"] == ("SYN-OPTION-TAIL-CREW-STAND")
    assert hitl_context["evidence_versions"] == context.observation["evidence_versions"]


@pytest.mark.parametrize(
    "invalid_case",
    [
        "impact_extra_key",
        "impact_wrong_phase",
        "impact_actor_ids",
        "impact_event_ids",
        "impact_summary_type",
        "ranking_wrong_phase",
        "ranking_duplicate",
        "ranking_drop",
        "ranking_invented",
        "ranking_reasoning_type",
    ],
)
def test_agent_outputs_are_strictly_validated(
    monkeypatch,
    invalid_case: str,
) -> None:
    context = AirlineContext(timeout=True)

    async def invalid_agent(prompt: str, **kwargs: Any) -> dict[str, Any]:
        phase = kwargs["phase"]
        if phase == "Assess Network Impact":
            result: dict[str, Any] = {
                "phase": phase,
                "actor_ids": context.observation["actor_ids"],
                "event_ids": context.observation["event_ids"],
                "impact_summary": "Versioned synthetic impact.",
            }
            if invalid_case == "impact_extra_key":
                result["recommendation"] = "invented"
            elif invalid_case == "impact_wrong_phase":
                result["phase"] = "Different phase"
            elif invalid_case == "impact_actor_ids":
                result["actor_ids"] = ["SYN-INVENTED-ACTOR"]
            elif invalid_case == "impact_event_ids":
                result["event_ids"] = ["evt-invented"]
            elif invalid_case == "impact_summary_type":
                result["impact_summary"] = ["not", "a", "string"]
            return result
        result = {
            "phase": phase,
            "ranked_option_ids": [
                "SYN-OPTION-TAIL-CREW-STAND",
                "SYN-OPTION-CANCEL",
            ],
            "reasoning": "Ranks all admitted options once.",
        }
        if invalid_case == "ranking_wrong_phase":
            result["phase"] = "Different phase"
        elif invalid_case == "ranking_duplicate":
            result["ranked_option_ids"] = [
                "SYN-OPTION-TAIL-CREW-STAND",
                "SYN-OPTION-TAIL-CREW-STAND",
            ]
        elif invalid_case == "ranking_drop":
            result["ranked_option_ids"] = ["SYN-OPTION-TAIL-CREW-STAND"]
        elif invalid_case == "ranking_invented":
            result["ranked_option_ids"] = [
                "SYN-OPTION-TAIL-CREW-STAND",
                "SYN-OPTION-INVENTED",
            ]
        elif invalid_case == "ranking_reasoning_type":
            result["reasoning"] = {"text": "not a string"}
        return result

    monkeypatch.setattr(durable, "run_agent_session", invalid_agent)

    with pytest.raises(ValueError, match="Airline agent"):
        drive_airline_orchestrator(context)


def test_live_agent_failure_propagates_without_deterministic_fallback(
    monkeypatch,
) -> None:
    context = AirlineContext()

    async def failed_agent(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("live Airline agent failed")

    monkeypatch.setattr(durable, "run_agent_session", failed_agent)

    with pytest.raises(RuntimeError, match="live Airline agent failed"):
        drive_airline_orchestrator(context)


def test_each_phase_receives_only_its_declared_tool_and_skill(
    monkeypatch,
) -> None:
    context = AirlineContext(timeout=True)
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        durable,
        "run_agent_session",
        _valid_agent(context, captured),
    )

    drive_airline_orchestrator(context)

    skill_root = Path(__file__).resolve().parents[3] / "verticals" / "airline" / "skills"
    assert [
        (
            item["phase"],
            item["skill_label"],
            item["skill_dir"],
            item["tools"],
        )
        for item in captured
    ] == [
        (
            "Assess Network Impact",
            "network-impact-assessor",
            skill_root / "network-impact-assessor",
            [operations.airline_read_disruption_evidence],
        ),
        (
            "Synthesize Recovery Options",
            "recovery-option-ranker",
            skill_root / "recovery-option-ranker",
            [operations.airline_rank_feasible_recovery_options],
        ),
    ]


def test_governance_kernel_receives_exact_authority_request_before_suspension(
    monkeypatch,
) -> None:
    context = AirlineContext(timeout=True)
    captured: list[dict[str, Any]] = []

    class CapturingKernel:
        def check_authority(self, **kwargs: Any) -> SimpleNamespace:
            captured.append(kwargs)
            return SimpleNamespace(
                allowed=True,
                reason="governed",
                governing_rule_id="AIRLINE-GOVERNED-001",
            )

    monkeypatch.setattr(durable, "kernel", lambda: CapturingKernel())
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    drive_airline_orchestrator(context)

    assert captured == [
        {
            "role": "duty_operations_manager",
            "action": "airline.commit_recovery_plan",
            "category": "synthetic-operational-recovery",
            "value": 75_000.0,
        }
    ]
    governance_index = next(
        index
        for index, (name, _) in enumerate(context.calls)
        if name == "airline_governance_activity_trigger"
    )
    suspension_index = next(
        index
        for index, (name, payload) in enumerate(context.calls)
        if name == "checkpoint_activity_trigger" and payload["kind"] == "suspended"
    )
    assert governance_index < suspension_index


def test_governance_denial_fails_closed_before_suspension(
    monkeypatch,
) -> None:
    context = AirlineContext()

    class DeniedKernel:
        def check_authority(self, **_kwargs: Any) -> SimpleNamespace:
            return SimpleNamespace(
                allowed=False,
                reason="outside delegated authority",
                governing_rule_id=None,
            )

    monkeypatch.setattr(durable, "kernel", lambda: DeniedKernel())
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "denied"
    assert result["reason"] == "outside delegated authority"
    assert result["command"] is None
    assert context.external_event is None


def test_command_activity_uses_world_gateway_without_terminal_claim(
    monkeypatch,
) -> None:
    context = AirlineContext(
        approval={
            "decision": "approve",
            "persona": "duty_operations_manager",
            "decision_id": "SYN-DECISION-001",
            "selected_option_id": "SYN-OPTION-TAIL-CREW-STAND",
        }
    )
    monkeypatch.setattr(durable, "run_agent_session", _valid_agent(context))

    result = drive_airline_orchestrator(context)

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == "airline.commit_recovery_plan"
    assert result["gateway_event"]["type"] == "command.accepted"
    assert context.world.recovery_commands[result["command"]["command_id"]]
    assert context.world.recovery_evaluations["AIRHUB-0001"]
    assert result["evaluation"] == {
        "status": "pending_world_event_pipeline",
        "success_event": "airline.recovery.applied",
    }
    checkpoint_kinds = [
        payload["kind"] for name, payload in context.calls if name == "checkpoint_activity_trigger"
    ]
    assert "workflow.completed" not in checkpoint_kinds
    assert result["status"] not in {"completed", "success", "succeeded"}


def test_exports_exactly_one_named_orchestrator() -> None:
    assert durable.ORCHESTRATOR == "AirlineIntegratedHubRecoveryOrchestrator"
    assert callable(durable.AirlineIntegratedHubRecoveryOrchestrator)


def test_duty_operations_manager_skill_is_governed_and_tool_free() -> None:
    skill_path = (
        Path(__file__).resolve().parents[3]
        / "verticals"
        / "airline"
        / "personae"
        / "duty_operations_manager"
        / "SKILL.md"
    )
    text = skill_path.read_text(encoding="utf-8")
    match = re.fullmatch(r"---\n(.*?)\n---\n(.*)", text, flags=re.DOTALL)
    assert match is not None
    frontmatter = yaml.safe_load(match.group(1))
    body = " ".join(match.group(2).lower().split())

    assert frontmatter["name"] == "duty_operations_manager"
    assert frontmatter["external_event"] == "duty_operations_manager_decision"
    assert "allowed-tools" not in frontmatter
    required_terms = {
        "deterministically admitted option",
        "gbp 150,000",
        "unresolved feasibility",
        "safety",
        "legality",
        "stale or missing evidence",
        "wrong story",
        "workflow",
        "persona",
        "above authority",
        "decision_id",
        "selected_option_id",
        "evidence_versions",
        "rationale",
        "duty_operations_manager_decision",
        "synthetic",
        "truth-mode",
        "no live",
    }
    assert all(term in body for term in required_terms)
