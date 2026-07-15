from api.server.world.commands import CommandGateway
from api.server.world.evaluations import OutcomeEvaluator
from api.server.world.model import SimulationCommand
from api.server.world.objectives import ObjectiveManager
from api.server.world.registry import ObjectiveRoute
from api.server.world.runtime import SimulationRuntime


ROUTE = ObjectiveRoute(
    sensor_id="sensor:test",
    objective_type="test_recovery",
    allowed_command_types=frozenset({"repair"}),
    success_event_types=frozenset({"asset.recovered"}),
    failure_event_types=frozenset({"asset.failed_permanently"}),
    evaluation_timeout_minutes=5,
)


def _sensor():
    return {
        "event_id": "evt-sensor",
        "trace_id": "trace-root",
        "target_id": "ASSET-1",
        "actor_id": "sensor:test",
        "payload": {"measurements": {"availability": 0}},
    }


def _acting(runtime, manager):
    objective = manager.open(_sensor(), ROUTE, owner_function="repair_agent")
    manager.transition(objective.id, "claimed", claimed_by="repair_agent")
    return manager.transition(objective.id, "acting")


def _command():
    return SimulationCommand(
        command_id="cmd-1",
        trace_id="trace-root",
        issued_by="repair_agent",
        type="repair",
        payload={},
    )


def test_success_event_resolves_evaluation_and_objective_from_journal_slice():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting(runtime, manager)
    evaluator = OutcomeEvaluator(runtime, manager)

    def apply(command):
        accepted = runtime.emit("command.accepted", trace_id=command.trace_id)
        runtime.emit(
            "asset.recovered",
            actor_id="ASSET-1",
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={"measurements": {"availability": 1}},
        )
        return accepted

    gateway = CommandGateway(runtime, manager, apply, evaluator)
    gateway.apply(objective, _command())

    evaluation = evaluator.evaluations[0]
    assert evaluation.status == "resolved"
    assert evaluation.final_measurements == {"availability": 1}
    assert len(evaluation.evidence_event_ids) == 1
    assert evaluation.completed_at == runtime.now
    assert manager.get(objective.id).status == "resolved"
    assert [event.type for event in runtime.journal][-2:] == [
        "objective.resolved",
        "evaluation.resolved",
    ]


def test_failure_event_fails_evaluation_and_objective():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting(runtime, manager)
    evaluator = OutcomeEvaluator(runtime, manager)

    def apply(command):
        accepted = runtime.emit("command.accepted", trace_id=command.trace_id)
        runtime.emit(
            "asset.failed_permanently",
            actor_id="ASSET-1",
            cause_event_id=accepted.event_id,
            trace_id=command.trace_id,
            payload={"reason": "hardware destroyed"},
        )
        return accepted

    CommandGateway(runtime, manager, apply, evaluator).apply(objective, _command())

    assert evaluator.evaluations[0].status == "failed"
    assert manager.get(objective.id).status == "failed"


def test_timeout_fails_evaluation_without_fabricated_evidence():
    runtime = SimulationRuntime(1)
    manager = ObjectiveManager(runtime)
    objective = _acting(runtime, manager)
    evaluator = OutcomeEvaluator(runtime, manager)

    def apply(command):
        return runtime.emit("command.accepted", trace_id=command.trace_id)

    CommandGateway(runtime, manager, apply, evaluator).apply(objective, _command())
    runtime.env.run(until=6)
    evaluator.observe(())

    evaluation = evaluator.evaluations[0]
    assert evaluation.status == "timed_out"
    assert evaluation.evidence_event_ids == ()
    assert manager.get(objective.id).status == "failed"
    assert runtime.journal[-1].type == "evaluation.timed_out"
