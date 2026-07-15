"""Unit proof for the command gateway's objective-scope enforcement.

Drives a real ``ObjectiveManager`` over a standalone runtime with a fake
scenario ``apply_command``, so the gateway's accept/reject rules and the
``evaluating`` + ``evaluation.started`` foundation are asserted directly against
the journal — no SimPy scenario or Durable host required.
"""
from __future__ import annotations

import pytest

from api.server.world.commands import CommandGateway
from api.server.world.evaluations import OutcomeEvaluator
from api.server.world.model import SimulationCommand
from api.server.world.objectives import ObjectiveManager
from api.server.world.registry import resolve_world_pack
from api.server.world.runtime import SimulationRuntime

TRACE = "support-pressure-5"
ISSUER = "surge_staffing"


def _sensor():
    return {
        "event_id": "evt-sensor",
        "trace_id": TRACE,
        "target_id": "queue:support",
        "type": "sensor.tripped",
        "payload": {"measurements": {"support_backlog": 12}},
    }


def _command(*, trace=TRACE, issuer=ISSUER, ctype="reallocate_workers"):
    return SimulationCommand(
        command_id="cmd-1", trace_id=trace, issued_by=issuer, type=ctype,
        payload={"worker_ids": ["WRK-1"]},
    )


def _accepting_apply(runtime):
    def apply(command):
        return runtime.emit(
            "command.accepted", trace_id=command.trace_id,
            payload={"command": command.to_dict()},
        )
    return apply


def _explode_apply(command):
    raise AssertionError("scenario apply must not run when the gateway rejects")


def _acting_objective(runtime, manager, *, issuer=ISSUER):
    route = resolve_world_pack("support").objective_routes[0]
    objective = manager.open(_sensor(), route, owner_function=issuer)
    manager.transition(objective.id, "claimed", claimed_by=issuer)
    manager.transition(objective.id, "acting")
    return manager.get(objective.id)


def test_accepts_valid_command_and_starts_evaluation():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting_objective(runtime, manager)
    evaluator = OutcomeEvaluator(runtime, manager)
    gateway = CommandGateway(runtime, manager, _accepting_apply(runtime), evaluator)

    result = gateway.apply(objective, _command())

    assert result.type == "command.accepted"
    assert manager.get(objective.id).status == "evaluating"
    types = [event.type for event in runtime.journal]
    assert "objective.evaluating" in types
    assert "evaluation.started" in types
    assert len(evaluator.evaluations) == 1
    evaluation = evaluator.evaluations[0]
    assert evaluation.objective_id == objective.id
    assert evaluation.baseline == {"support_backlog": 12}
    started = next(event for event in runtime.journal if event.type == "evaluation.started")
    assert started.trace_id == TRACE


def test_rejects_when_objective_not_acting():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    route = resolve_world_pack("support").objective_routes[0]
    objective = manager.open(_sensor(), route, owner_function=ISSUER)
    manager.transition(objective.id, "claimed", claimed_by=ISSUER)  # still claimed, not acting
    gateway = CommandGateway(runtime, manager, _explode_apply)

    result = gateway.apply(manager.get(objective.id), _command())

    assert result.type == "command.rejected"
    assert manager.get(objective.id).status == "failed"
    assert gateway.evaluator.evaluations == []


@pytest.mark.parametrize(
    "command",
    [
        _command(trace="other-trace"),
        _command(ctype="reroute_sessions"),
        _command(issuer="intruder"),
    ],
    ids=["trace-mismatch", "type-not-allowed", "issuer-mismatch"],
)
def test_rejects_out_of_scope_command_without_mutation(command):
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting_objective(runtime, manager)
    gateway = CommandGateway(runtime, manager, _explode_apply)

    result = gateway.apply(objective, command)

    assert result.type == "command.rejected"
    assert manager.get(objective.id).status == "failed"
    assert gateway.evaluator.evaluations == []


def test_scenario_rejection_fails_objective_without_evaluation():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting_objective(runtime, manager)

    def rejecting_apply(command):
        return runtime.emit(
            "command.rejected", trace_id=command.trace_id, payload={"reason": "domain invalid"}
        )

    gateway = CommandGateway(runtime, manager, rejecting_apply)

    result = gateway.apply(objective, _command())

    assert result.type == "command.rejected"
    assert manager.get(objective.id).status == "failed"
    assert gateway.evaluator.evaluations == []
    assert "evaluation.started" not in [event.type for event in runtime.journal]
