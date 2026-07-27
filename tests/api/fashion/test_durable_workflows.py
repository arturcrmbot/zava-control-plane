from __future__ import annotations

from datetime import datetime
from importlib import import_module
from typing import Any

import pytest

from verticals.fashion.domains import FASHION_DOMAINS
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.reference_cases import FASHION_REFERENCE_CASES


class _Task:
    def __init__(self, result=None):
        self.result = result
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class _Context:
    instance_id = "fashion-instance-1"
    current_utc_datetime = datetime(2026, 7, 22)

    def __init__(
        self,
        workflow_type: str,
        *,
        policy_decision: str = "approval_required",
        approval: dict[str, Any] | None = None,
        story_id: str | None = None,
    ) -> None:
        profile = FASHION_PROCESS_PROFILES[workflow_type]
        case = FASHION_REFERENCE_CASES[workflow_type]
        observation = {
            "workflow_type": workflow_type,
            "case": {
                "id": case.id,
                "workflow_type": workflow_type,
                "subject_ids": list(case.subject_ids),
                "facts": dict(case.facts),
                "allowed_actions": list(case.allowed_actions),
            },
            "actor_ids": list(case.subject_ids),
            "event_ids": ["evt-00000142"],
            "trace_id": f"trace-{workflow_type}",
            "as_of_sim_time": 42.0,
            "skills": list(FASHION_DOMAINS[workflow_type].skills),
            "mcp_tools": [f"fashion-{workflow_type}"],
            "authority": {
                "persona": profile.hitl_persona,
                "external_event": profile.hitl_event,
            },
            "typed_command": profile.command_type,
        }
        if story_id is not None:
            observation["story_id"] = story_id
        if workflow_type == "inventory-rebalancing":
            observation.update(
                {
                    "transfer_candidate": {
                        "source_location_id": "STORE-EU-PAR-01",
                        "destination_location_id": "STORE-UK-LON-01",
                        "sku_id": "SKU-STYLE-01-BLK-M",
                        "quantity": 24,
                        "ownership": "owned",
                        "expected_source_version": 1,
                        "expected_destination_version": 5,
                    },
                    "policy": {
                        "decision": policy_decision,
                        "reason": (
                            "cross-border transfer"
                            if policy_decision == "approval_required"
                            else "within bounded autonomy"
                        ),
                    },
                }
            )
        self._input = {
            "workflow_id": f"{profile.prefix}-evt-00000142",
            "trace_id": f"trace-{workflow_type}",
            "type": workflow_type,
            "observation": observation,
        }
        self.approval = _Task(approval)
        self.timer = _Task()
        self.external_event: str | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        durable = import_module("verticals.fashion.durable")
        if name == "fashion_evidence_activity_trigger":
            return durable.fashion_evidence_activity(payload)
        if name == "fashion_decision_activity_trigger":
            return durable.fashion_decision_activity(payload)
        if name == "fashion_command_activity_trigger":
            return durable.fashion_command_activity(payload)
        return {"checkpoint": payload["kind"]}

    def wait_for_external_event(self, name):
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, _tasks):
        return self.approval


def _drive(context: _Context) -> dict[str, Any]:
    durable = import_module("verticals.fashion.durable")
    generator = durable.fashion_orchestration(context)
    sent: Any = None
    while True:
        try:
            yielded = generator.send(sent) if sent is not None else next(generator)
        except StopIteration as stop:
            return stop.value
        sent = yielded


@pytest.mark.parametrize("workflow_type", tuple(FASHION_PROCESS_PROFILES))
def test_all_eight_orchestrators_return_their_typed_command(
    workflow_type: str,
) -> None:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    context = _Context(
        workflow_type,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "decision_id": f"HITL-{profile.prefix.upper()}-001",
        },
    )

    result = _drive(context)

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == profile.command_type
    assert result["command"]["trace_id"] == f"trace-{workflow_type}"
    assert result["command"]["issued_by"] == profile.function
    assert result["workflow_evidence"]["actor_ids"]
    assert result["reasoning"]["skill_outputs"]
    checkpoint_kinds = [
        payload["kind"]
        for name, payload in context.calls
        if name == "checkpoint_activity_trigger"
    ]
    assert checkpoint_kinds[0] == "workflow.started"
    assert "workflow.completed" not in checkpoint_kinds


def test_policy_safe_hero_skips_hitl_but_preserves_authority_evidence() -> None:
    context = _Context(
        "inventory-rebalancing",
        policy_decision="auto_safe",
    )

    result = _drive(context)

    assert context.external_event is None
    assert result["approval"]["decision"] == "not_required"
    assert result["approval"]["authority_persona"] == "merchandising_director"
    assert result["command"]["payload"]["approval_reference"] is None


def test_cross_border_hero_waits_for_exact_authority_event() -> None:
    context = _Context(
        "inventory-rebalancing",
        approval={
            "decision": "approve",
            "persona": "merchandising_director",
            "decision_id": "HITL-MERCH-001",
        },
    )

    result = _drive(context)

    assert context.external_event == "merchandising_director_decision"
    assert result["approval"]["persona"] == "merchandising_director"
    assert result["command"]["payload"]["approval_reference"] == "HITL-MERCH-001"
    assert result["command"]["payload"]["expected_source_version"] == 1
    assert result["command"]["payload"]["expected_destination_version"] == 5


@pytest.mark.parametrize(
    "workflow_type",
    ("inventory-rebalancing", "demand-spike-response"),
)
def test_typed_command_propagates_story_id(workflow_type: str) -> None:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    context = _Context(
        workflow_type,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "decision_id": f"HITL-{profile.prefix.upper()}-STORY",
        },
        story_id="fashion-trading-shock-42",
    )

    result = _drive(context)

    assert result["command"]["payload"]["story_id"] == "fashion-trading-shock-42"


@pytest.mark.parametrize(
    "approval",
    [
        {"decision": "reject", "persona": "merchandising_director"},
        {"decision": "approve", "persona": "fulfilment_manager"},
    ],
)
def test_hitl_denial_or_wrong_persona_fails_closed(approval) -> None:
    context = _Context("inventory-rebalancing", approval=approval)

    result = _drive(context)

    assert result["status"] == "denied"
    assert result["command"] is None


def test_command_activity_rejects_missing_real_actor_evidence() -> None:
    durable = import_module("verticals.fashion.durable")
    context = _Context(
        "returns-disposition",
        approval={
            "decision": "approve",
            "persona": "returns_operations_manager",
            "decision_id": "HITL-RETURN-001",
        },
    )
    payload = context.get_input()
    payload["observation"] = {**payload["observation"], "actor_ids": []}

    with pytest.raises(ValueError, match="actor_ids"):
        durable.fashion_evidence_activity(payload)


def test_durable_module_registers_exactly_eight_named_orchestrators() -> None:
    durable = import_module("verticals.fashion.durable")

    for profile in FASHION_PROCESS_PROFILES.values():
        assert callable(getattr(durable, profile.orchestrator))
    assert durable.ORCHESTRATOR_NAMES == frozenset(
        profile.orchestrator for profile in FASHION_PROCESS_PROFILES.values()
    )


def test_hybrid_mode_uses_ghcp_session_for_selected_workflow(
    monkeypatch,
) -> None:
    durable = import_module("verticals.fashion.durable")
    context = _Context("inventory-rebalancing")
    payload = {
        **context.get_input(),
        "instance_id": "fashion-live-instance",
        "phase": "Assess Demand and Constraints",
        "prior_outputs": {},
    }
    captured: dict[str, Any] = {}

    async def fake_run_agent_session(prompt: str, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return {
            "skill": "inventory-imbalance-analysis",
            "phase": "Assess Demand and Constraints",
            "recommendation": "inventory.transfer",
            "actor_ids": payload["observation"]["actor_ids"],
            "event_ids": payload["observation"]["event_ids"],
            "constraints": {
                "ownership": "explicit",
                "authority": "merchandising_director",
                "stale_evidence": "reject",
            },
            "reasoning": "Live agent correlated demand and inventory evidence.",
            "_raw_tool_calls": [
                {
                    "name": "report_intent",
                    "success": True,
                },
                {
                    "name": "fashion_read_inventory",
                    "success": True,
                }
            ],
        }

    monkeypatch.setenv("ZAVA_FASHION_AGENT_MODE", "hybrid")
    monkeypatch.setenv(
        "ZAVA_FASHION_LIVE_WORKFLOWS",
        "inventory-rebalancing,markdown-governance",
    )
    monkeypatch.setattr(durable, "run_agent_session", fake_run_agent_session)

    result = durable.fashion_decision_activity(payload)

    assert result["reasoning"].startswith("Live agent")
    assert captured["workflow_id"] == payload["workflow_id"]
    assert captured["instance_id"] == "fashion-live-instance"
    assert captured["phase"] == "Assess Demand and Constraints"
    assert captured["skill_label"] == "inventory-imbalance-analysis"
    assert captured["tools"]


def test_hybrid_mode_keeps_unselected_workflow_deterministic(
    monkeypatch,
) -> None:
    durable = import_module("verticals.fashion.durable")
    context = _Context("demand-spike-response")
    payload = {
        **context.get_input(),
        "instance_id": "fashion-deterministic-instance",
        "phase": "Assess Stock Exposure",
        "prior_outputs": {},
    }

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unselected workflow must not open an agent session")

    monkeypatch.setenv("ZAVA_FASHION_AGENT_MODE", "hybrid")
    monkeypatch.setenv(
        "ZAVA_FASHION_LIVE_WORKFLOWS",
        "inventory-rebalancing,markdown-governance",
    )
    monkeypatch.setattr(durable, "run_agent_session", fail_if_called)

    result = durable.fashion_decision_activity(payload)

    assert result["skill"] == "inventory-imbalance-analysis"
    assert result["reasoning"].startswith("inventory-imbalance-analysis selected")
