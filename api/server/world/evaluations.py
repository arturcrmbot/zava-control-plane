"""Evidence-backed terminal evaluation for accepted world commands."""
from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from api.server.world.model import Evaluation, Objective, SimulationCommand, SimulationEvent
from api.server.world.objectives import ObjectiveManager
from api.server.world.registry import ObjectiveRoute
from api.server.world.runtime import SimulationRuntime


class OutcomeEvaluator:
    """Matches world evidence to active evaluations on the objective trace."""

    def __init__(self, runtime: SimulationRuntime, objectives: ObjectiveManager) -> None:
        self._runtime = runtime
        self._objectives = objectives
        self._evaluations: list[Evaluation] = []
        self._route_by_evaluation: dict[str, ObjectiveRoute] = {}

    @property
    def evaluations(self) -> list[Evaluation]:
        return list(self._evaluations)

    def for_objective(self, objective_id: str) -> Evaluation | None:
        return next(
            (item for item in reversed(self._evaluations) if item.objective_id == objective_id),
            None,
        )

    def start(
        self,
        objective: Objective,
        command: SimulationCommand,
        route: ObjectiveRoute,
        *,
        cause_event_id: str | None,
    ) -> Evaluation:
        evaluation = Evaluation(
            id=f"eval-{command.command_id}",
            objective_id=objective.id,
            trace_id=command.trace_id,
            command_id=command.command_id,
            started_at=self._runtime.now,
            baseline=self._objectives.baseline_for(objective.id),
            deadline_at=self._runtime.now + route.evaluation_timeout_minutes,
        )
        self._evaluations.append(evaluation)
        self._route_by_evaluation[evaluation.id] = route
        self._runtime.emit(
            "evaluation.started",
            actor_id=objective.owner_function,
            target_id=objective.claimed_by,
            cause_event_id=cause_event_id,
            trace_id=command.trace_id,
            payload=evaluation.to_dict(),
        )
        return evaluation

    def observe(self, events: Iterable[SimulationEvent]) -> None:
        evidence = tuple(events)
        for evaluation in tuple(self._evaluations):
            if evaluation.status != "started":
                continue
            route = self._route_by_evaluation[evaluation.id]
            matched = next(
                (
                    event
                    for event in evidence
                    if event.trace_id == evaluation.trace_id
                    and event.type
                    in (route.success_event_types | route.failure_event_types)
                ),
                None,
            )
            if matched is not None:
                status = (
                    "resolved"
                    if matched.type in route.success_event_types
                    else "failed"
                )
                self._finish(evaluation, status, matched)
            elif (
                evaluation.deadline_at is not None
                and self._runtime.now >= evaluation.deadline_at
            ):
                self._finish(evaluation, "timed_out", None)

    def _finish(
        self,
        evaluation: Evaluation,
        status: str,
        evidence: SimulationEvent | None,
    ) -> None:
        objective_status = "resolved" if status == "resolved" else "failed"
        objective = self._objectives.get(evaluation.objective_id)
        if objective is None or objective.status != "evaluating":
            return

        evidence_ids = (evidence.event_id,) if evidence is not None else ()
        final_measurements = None
        if evidence is not None:
            payload = evidence.payload or {}
            final_measurements = dict(payload.get("measurements") or payload)
        updated = replace(
            evaluation,
            status=status,
            final_measurements=final_measurements,
            evidence_event_ids=evidence_ids,
            completed_at=self._runtime.now,
        )
        index = self._evaluations.index(evaluation)
        self._evaluations[index] = updated
        self._objectives.transition(
            evaluation.objective_id,
            objective_status,
            cause_event_id=evidence.event_id if evidence is not None else None,
            evidence_event_id=evidence.event_id if evidence is not None else None,
            payload={"evaluation_id": evaluation.id, "evaluation_status": status},
        )
        self._runtime.emit(
            f"evaluation.{status}",
            actor_id=objective.owner_function,
            target_id=objective.claimed_by,
            cause_event_id=self._objectives.last_event_id(evaluation.objective_id),
            trace_id=evaluation.trace_id,
            payload=updated.to_dict(),
        )
