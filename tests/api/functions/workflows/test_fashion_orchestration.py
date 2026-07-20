from datetime import datetime
from typing import Any

import pytest

from api.server.world.runtime import SimulationRuntime
from verticals.fashion.durable import (
    fashion_command_activity,
    fashion_orchestration,
    fashion_skill_activity,
)
from verticals.fashion.process_profiles import FASHION_PROCESS_PROFILES
from verticals.fashion.world import FashionScenario


class _Task:
    def __init__(self, result=None):
        self.result = result

    def cancel(self):
        return None


class _Context:
    instance_id = "fashion-instance-1"
    current_utc_datetime = datetime(2026, 7, 20)

    def __init__(
        self,
        workflow_type: str,
        *,
        requires_approval: bool,
        approval: dict[str, Any] | None = None,
    ):
        scenario = FashionScenario.demo(SimulationRuntime(20260720))
        scenario.install()
        result = scenario.run_case(workflow_type)
        sensor = next(
            event
            for event in scenario.runtime.journal
            if event.event_id == result["sensor_event_id"]
        )
        self._input = {
            "agent_mode": "deterministic",
            "workflow_id": f"WF-{workflow_type}",
            "trace_id": result["trace_id"],
            "type": workflow_type,
            "requires_approval": requires_approval,
            "observation": scenario.build_observation(
                sensor.to_dict(),
                now=scenario.runtime.now,
            ),
        }
        self.approval = _Task(approval)
        self.timer = _Task()
        self.external_event = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        self.calls.append((name, payload))
        if name == "fashion_skill_activity_trigger":
            return fashion_skill_activity(payload)
        if name == "fashion_command_activity_trigger":
            return fashion_command_activity(payload)
        return {}

    def wait_for_external_event(self, name):
        self.external_event = name
        return self.approval

    def create_timer(self, _deadline):
        return self.timer

    def task_any(self, _tasks):
        return self.approval


def _drive(context: _Context, workflow_type: str) -> dict[str, Any]:
    generator = fashion_orchestration(context, workflow_type)
    sent: Any = None
    while True:
        try:
            yielded = (
                generator.send(sent) if sent is not None else next(generator)
            )
        except StopIteration as stop:
            return stop.value
        sent = yielded


@pytest.mark.parametrize("workflow_type", FASHION_PROCESS_PROFILES)
def test_each_fashion_orchestration_returns_its_distinct_typed_command(
    workflow_type: str,
) -> None:
    profile = FASHION_PROCESS_PROFILES[workflow_type]
    context = _Context(
        workflow_type,
        requires_approval=True,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": f"approval:{profile.hitl_persona}:001",
        },
    )

    result = _drive(context, workflow_type)

    assert result["status"] == "decision_ready"
    assert result["command"]["type"] == profile.command_type
    assert result["command"]["payload"]["workflow_id"] == (
        f"WF-{workflow_type}"
    )
    invoked_skills = [
        payload["skill"]
        for name, payload in context.calls
        if name == "fashion_skill_activity_trigger"
    ]
    assert invoked_skills == list(profile.skills)
    assert context.external_event == profile.hitl_event


def test_policy_safe_inventory_rebalancing_skips_hitl() -> None:
    context = _Context(
        "inventory-rebalancing",
        requires_approval=False,
    )

    result = _drive(context, "inventory-rebalancing")

    assert context.external_event is None
    assert result["status"] == "decision_ready"
    assert result["command"]["payload"]["policy_decision"] == "auto_approved"
    assert result["command"]["payload"]["approval_reference"] is None


def test_governed_inventory_rebalancing_carries_approval_reference() -> None:
    profile = FASHION_PROCESS_PROFILES["inventory-rebalancing"]
    context = _Context(
        profile.workflow_type,
        requires_approval=True,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": "approval:merchandising-director:002",
        },
    )

    result = _drive(context, profile.workflow_type)

    assert result["command"]["payload"]["policy_decision"] == (
        "approval_required"
    )
    assert result["command"]["payload"]["approval_reference"] == (
        "approval:merchandising-director:002"
    )


def _payload_annotation(trigger) -> str:
    # Azure Functions wraps decorated triggers in a FunctionBuilder; the raw
    # user function carries the annotations the Python worker validates.
    user_function = trigger._function.get_user_function()
    return str(user_function.__annotations__["payload"])


def test_fashion_activity_triggers_use_worker_safe_payload_annotations() -> None:
    # The Azure Functions Python worker rejects parameterised generics such as
    # ``dict[str, Any]`` on a binding parameter ("invalid non-type
    # annotation"), which stops the whole host from indexing. Telco activity
    # triggers annotate ``payload: dict``; Fashion must too.
    from verticals.fashion import durable

    for name in (
        "fashion_skill_activity_trigger",
        "fashion_command_activity_trigger",
    ):
        annotation = _payload_annotation(getattr(durable, name))
        assert annotation == "dict", f"{name} payload annotation is {annotation!r}"


class _AmbientContext:
    """Mirrors the live WorldBridge payload for the ambient (auto-approved)
    flow: it carries NO ``requires_approval`` flag, exactly like
    ``api/server/services/world_bridge.py`` schedules the orchestration."""

    instance_id = "ambient-instance"
    current_utc_datetime = datetime(2026, 7, 20)

    def __init__(self, scenario: FashionScenario, workflow_type: str):
        result = scenario.run_case(workflow_type)
        sensor = next(
            event
            for event in scenario.runtime.journal
            if event.event_id == result["sensor_event_id"]
        )
        self._input = {
            "workflow_id": f"WF-{workflow_type}",
            "type": workflow_type,
            "trace_id": result["trace_id"],
            "observation": scenario.build_observation(
                sensor.to_dict(), now=scenario.runtime.now
            ),
        }

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        if name == "fashion_skill_activity_trigger":
            return fashion_skill_activity(payload)
        if name == "fashion_command_activity_trigger":
            return fashion_command_activity(payload)
        return {}

    def wait_for_external_event(self, name):
        return _Task()

    def create_timer(self, _deadline):
        return _Task()

    def task_any(self, _tasks):
        return _Task()


@pytest.mark.parametrize("workflow_type", FASHION_PROCESS_PROFILES)
def test_ambient_workflow_command_is_accepted_by_the_world(
    workflow_type: str,
) -> None:
    from api.server.world.model import SimulationCommand
    from api.server.world.runtime import SimulationRuntime

    scenario = FashionScenario.demo(SimulationRuntime(42))
    scenario.install()
    context = _AmbientContext(scenario, workflow_type)

    output = _drive(context, workflow_type)
    assert output["status"] == "decision_ready"

    command = SimulationCommand(**output["command"])
    applied = scenario.apply_command(command)

    assert applied.type == "command.accepted", applied.payload.get("reason")
