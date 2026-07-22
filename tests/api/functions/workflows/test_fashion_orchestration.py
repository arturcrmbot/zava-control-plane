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
        self.scenario = scenario
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


def test_orchestration_reads_approval_requirement_from_world_observation() -> None:
    profile = FASHION_PROCESS_PROFILES["demand-spike-response"]
    context = _Context(
        profile.workflow_type,
        requires_approval=False,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": "approval:inventory-allocation-manager:visible-demo",
        },
    )
    del context._input["requires_approval"]
    context._input["observation"]["requires_approval"] = True

    result = _drive(context, profile.workflow_type)

    assert context.external_event == profile.hitl_event
    assert result["status"] == "decision_ready"


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

    payload = result["command"]["payload"]
    assert payload["policy_decision"] == "approval_required"
    assert payload["approval_reference"] == "approval:merchandising-director:002"
    # The world's generic governed-transfer approval validator
    # (FashionScenario._validate_governed_transfer_approval) authenticates
    # every conditional inventory-transfer exception against the Fashion
    # authority model, so a legitimate HITL response must carry the typed
    # approving role and the source version it was granted against — not
    # just a free-form reference string.
    assert payload["approval_role"] == profile.hitl_persona
    assert payload["approved_source_version"] == (
        context._input["observation"]["command_payload"][
            "expected_source_version"
        ]
    )


def test_governed_inventory_rebalancing_carries_same_namespace_recommender_and_approver() -> None:
    """The Durable command activity — not a hand-built SimulationCommand —
    must stamp the recommendation-generating persona (``recommended_by``)
    and the approving persona (``approval_role``) in the SAME Fashion
    authority-persona namespace, so the world's self-approval guard
    (which compares these two payload fields) can ever actually fire in
    production. ``command["issued_by"]`` stays the function label
    (``merchandising_planning``) that ``CommandGateway`` needs for
    objective-ownership matching — it is a different concern and must not
    be conflated with either persona identity."""
    profile = FASHION_PROCESS_PROFILES["inventory-rebalancing"]
    context = _Context(
        profile.workflow_type,
        requires_approval=True,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": "approval:merchandising-director:003",
        },
    )

    result = _drive(context, profile.workflow_type)

    command = result["command"]
    payload = command["payload"]
    assert payload["recommended_by"] == "inventory_allocation_manager"
    assert payload["approval_role"] == "merchandising_director"
    assert payload["recommended_by"] != payload["approval_role"]
    # issued_by is the function label the CommandGateway checks — a
    # disjoint namespace from either persona above.
    assert command["issued_by"] == "merchandising_planning"


def test_real_hitl_response_self_approval_is_rejected_without_mutating_world() -> None:
    """A malicious or misconfigured HITL response that stamps the SAME
    persona as both the recommender and the approver must be rejected by
    the world when the resulting real Durable command payload is applied
    — not merely by a hand-built SimulationCommand."""
    profile = FASHION_PROCESS_PROFILES["inventory-rebalancing"]
    context = _Context(
        profile.workflow_type,
        requires_approval=True,
        approval={
            "decision": "approve",
            # Self-approval: the HITL responder stamps the recommender's
            # own persona as the approving role.
            "persona": "inventory_allocation_manager",
            "approval_role": "inventory_allocation_manager",
            "approval_reference": "approval:inventory_allocation_manager:self-001",
        },
    )
    scenario = context.scenario
    source = scenario.inventory[
        context._input["observation"]["command_payload"]["source_position_id"]
    ]
    before_on_hand = source.on_hand

    result = _drive(context, profile.workflow_type)
    assert result["status"] == "decision_ready"

    from api.server.world.model import SimulationCommand

    command = SimulationCommand(**result["command"])
    rejected = scenario.apply_command(command)

    assert rejected.type == "command.rejected"
    assert "self" in rejected.payload["reason"]
    assert source.on_hand == before_on_hand


def test_real_hitl_response_distinct_recommender_and_approver_succeeds() -> None:
    """The legitimate operator/recommender persona (inventory_allocation_
    manager) followed by a distinct approver persona (merchandising_
    director) must be accepted end-to-end through the real Durable
    command payload."""
    profile = FASHION_PROCESS_PROFILES["inventory-rebalancing"]
    context = _Context(
        profile.workflow_type,
        requires_approval=True,
        approval={
            "decision": "approve",
            "persona": profile.hitl_persona,
            "approval_reference": "approval:merchandising-director:004",
        },
    )
    scenario = context.scenario
    command_payload = context._input["observation"]["command_payload"]
    source = scenario.inventory[command_payload["source_position_id"]]
    destination = scenario.inventory[command_payload["destination_position_id"]]
    quantity = command_payload["quantity"]
    source_before = source.on_hand
    destination_before = destination.on_hand

    result = _drive(context, profile.workflow_type)
    assert result["status"] == "decision_ready"

    from api.server.world.model import SimulationCommand

    command = SimulationCommand(**result["command"])
    accepted = scenario.apply_command(command)

    assert accepted.type == "command.accepted"
    assert source.on_hand == source_before - quantity
    assert destination.on_hand == destination_before + quantity


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
    """Mirrors the live WorldBridge payload and autonomous persona response."""

    instance_id = "ambient-instance"
    current_utc_datetime = datetime(2026, 7, 20)

    def __init__(self, scenario: FashionScenario, workflow_type: str):
        profile = FASHION_PROCESS_PROFILES[workflow_type]
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
        self.approval = _Task(
            {
                "decision": "approve",
                "persona": profile.hitl_persona,
                "approval_reference": f"approval:{profile.hitl_persona}:ambient",
            }
        )

    def get_input(self):
        return self._input

    def call_activity(self, name, payload):
        if name == "fashion_skill_activity_trigger":
            return fashion_skill_activity(payload)
        if name == "fashion_command_activity_trigger":
            return fashion_command_activity(payload)
        return {}

    def wait_for_external_event(self, name):
        return self.approval

    def create_timer(self, _deadline):
        return _Task()

    def task_any(self, _tasks):
        return self.approval


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
