"""Command gateway — enforces objective command scope before mutation.

The bridge no longer applies a Durable command straight into the scenario. It
routes it through :class:`CommandGateway`, which checks the command against the
claimed objective (status, trace, allowed type, claimed issuer) and only then
delegates the actual mutation — and all domain validation — to the scenario's
own ``apply_command``. An accepted mutation moves the objective to
``evaluating`` and opens a frozen :class:`~api.server.world.model.Evaluation`
seeded with the objective's baseline sensor measurements. A rejection (by the
gateway or by the scenario) journals ``command.rejected`` and fails the
objective.

No scenario validation is duplicated here, and no effectiveness is judged: the
evaluation only ever reaches ``started``. Completing it belongs to the coupled
systemic slice (documented as Plan B in ARCHITECTURE §15).
"""
from __future__ import annotations

from collections.abc import Callable

from api.server.world.model import Evaluation, Objective, SimulationCommand, SimulationEvent
from api.server.world.objectives import ObjectiveManager
from api.server.world.runtime import SimulationRuntime


class CommandGateway:
    """Validates a typed command against its objective, then delegates mutation."""

    def __init__(
        self,
        runtime: SimulationRuntime,
        objectives: ObjectiveManager,
        apply_scenario_command: Callable[[SimulationCommand], SimulationEvent],
    ) -> None:
        self._runtime = runtime
        self._objectives = objectives
        self._apply_scenario = apply_scenario_command
        self.evaluations: list[Evaluation] = []

    def apply(self, objective: Objective, command: SimulationCommand) -> SimulationEvent:
        """Apply ``command`` under ``objective`` and return the resulting event.

        Returns the scenario mutation event on acceptance (objective →
        ``evaluating``) or the ``command.rejected`` event on any rejection
        (objective → ``failed``).
        """
        # Always evaluate against the live objective, not a stale snapshot.
        objective = self._objectives.get(objective.id) or objective

        reason = self._reject_reason(objective, command)
        if reason is not None:
            rejected = self._runtime.emit(
                "command.rejected",
                actor_id=command.issued_by,
                target_id=objective.claimed_by,
                cause_event_id=self._objectives.last_event_id(objective.id),
                trace_id=command.trace_id,
                payload={"command": command.to_dict(), "reason": reason},
            )
            self._objectives.transition(
                objective.id, "failed", cause_event_id=rejected.event_id,
                payload={"reason": reason},
            )
            return rejected

        result = self._apply_scenario(command)
        if result.type == "command.rejected":
            # Scenario applied its own validation and refused the mutation.
            self._objectives.transition(
                objective.id, "failed", cause_event_id=result.event_id,
                payload={"reason": "scenario rejected command"},
            )
            return result

        self._objectives.transition(
            objective.id, "evaluating",
            cause_event_id=result.event_id, evidence_event_id=result.event_id,
        )
        evaluation = Evaluation(
            id=f"eval-{command.command_id}",
            objective_id=objective.id,
            trace_id=command.trace_id,
            command_id=command.command_id,
            started_at=self._runtime.now,
            baseline=self._objectives.baseline_for(objective.id),
        )
        self.evaluations.append(evaluation)
        self._runtime.emit(
            "evaluation.started",
            actor_id=objective.owner_function,
            target_id=objective.claimed_by,
            cause_event_id=result.event_id,
            trace_id=command.trace_id,
            payload=evaluation.to_dict(),
        )
        return result

    def _reject_reason(self, objective: Objective, command: SimulationCommand) -> str | None:
        if objective.status != "acting":
            return f"objective {objective.id} is {objective.status}, not acting"
        if command.trace_id != objective.trace_id:
            return "command trace does not match objective trace"
        if command.type not in objective.allowed_command_types:
            return f"command type {command.type!r} not allowed for objective"
        if command.issued_by != objective.claimed_by:
            return f"issuer {command.issued_by!r} did not claim the objective"
        return None
