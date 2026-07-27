from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any, Mapping


STAGE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "demand-spike-response": (),
    "inventory-rebalancing": (),
    "promotion-readiness": ("demand-spike-response", "inventory-rebalancing"),
    "supplier-delay-recovery": ("demand-spike-response",),
    "marketplace-seller-exception": ("demand-spike-response",),
    "fulfilment-exception-resolution": (
        "inventory-rebalancing",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
    ),
    "markdown-governance": ("inventory-rebalancing",),
    "returns-disposition": ("promotion-readiness", "fulfilment-exception-resolution"),
}

STAGE_AUTONOMY: dict[str, str] = {
    "demand-spike-response": "policy-safe",
    "inventory-rebalancing": "policy-safe",
    "promotion-readiness": "human-approved",
    "supplier-delay-recovery": "human-approved",
    "marketplace-seller-exception": "human-approved",
    "fulfilment-exception-resolution": "human-approved",
    "markdown-governance": "human-approved",
    "returns-disposition": "human-approved",
}

TITLE = "The viral summer drop"


@dataclass(slots=True)
class StoryStage:
    workflow_type: str
    dependency_ids: tuple[str, ...]
    status: str = "waiting"
    sensor_event_id: str | None = None
    workflow_id: str | None = None
    autonomy: str = "human-approved"
    reason: str | None = None

    def view(self) -> dict[str, Any]:
        return {
            "workflow_type": self.workflow_type,
            "dependency_ids": list(self.dependency_ids),
            "status": self.status,
            "sensor_event_id": self.sensor_event_id,
            "workflow_id": self.workflow_id,
            "autonomy": self.autonomy,
            "reason": self.reason,
        }


@dataclass(slots=True)
class TradingShockState:
    seed: int
    id: str = field(init=False)
    trace_id: str | None = field(init=False, default=None)
    status: str = field(init=False, default="idle")
    cause_event_id: str | None = field(init=False, default=None)
    started_at_sim_time: float | None = field(init=False, default=None)
    _stages: dict[str, StoryStage] = field(init=False, repr=False)
    failure: dict[str, Any] | None = field(init=False, default=None)
    _baseline: dict[str, Any] | None = field(init=False, default=None, repr=False)
    _outcome: dict[str, Any] | None = field(init=False, default=None, repr=False)

    def __post_init__(self) -> None:
        self.id = f"trading-shock:{self.seed}"
        self._stages = {
            workflow_type: StoryStage(
                workflow_type=workflow_type,
                dependency_ids=dependency_ids,
                autonomy=STAGE_AUTONOMY[workflow_type],
            )
            for workflow_type, dependency_ids in STAGE_DEPENDENCIES.items()
        }

    def start(
        self,
        cause_event_id: str,
        trace_id: str,
        sim_time: float,
        baseline: Mapping[str, Any],
    ) -> None:
        if self.status != "idle":
            raise ValueError("trading shock can only be started from idle")
        self.id = trace_id
        self.trace_id = trace_id
        self.cause_event_id = cause_event_id
        self.started_at_sim_time = sim_time
        self.status = "running"
        self.failure = None
        self._baseline = deepcopy(dict(baseline))
        self._outcome = None

    def ready_to_trigger(self) -> tuple[StoryStage, ...]:
        if self.status != "running":
            return ()
        return tuple(
            replace(stage)
            for workflow_type, stage in self._stages.items()
            if stage.status == "waiting"
            and all(self._stages[dependency_id].status == "completed" for dependency_id in stage.dependency_ids)
        )

    def mark_triggered(
        self,
        workflow_type: str,
        *,
        sensor_event_id: str,
        reason: str | None = None,
    ) -> None:
        stage = self._stage(workflow_type)
        self._ensure_running()
        if stage.status != "waiting":
            raise ValueError(f"stage {workflow_type!r} cannot be triggered from {stage.status!r}")
        if stage not in self.ready_to_trigger():
            raise ValueError(f"stage {workflow_type!r} is not ready to trigger")
        stage.status = "triggered"
        stage.sensor_event_id = sensor_event_id
        stage.reason = reason

    def bind_workflow(
        self,
        workflow_type: str,
        *,
        workflow_id: str,
        autonomy: str | None = None,
    ) -> None:
        stage = self._stage(workflow_type)
        self._ensure_running()
        if stage.status == "active":
            if stage.workflow_id != workflow_id:
                raise ValueError(
                    f"stage {workflow_type!r} already bound to {stage.workflow_id!r}"
                )
            if autonomy is not None:
                stage.autonomy = autonomy
            return
        if stage.status != "triggered":
            raise ValueError(f"stage {workflow_type!r} cannot bind workflow from {stage.status!r}")
        stage.workflow_id = workflow_id
        if autonomy is not None:
            stage.autonomy = autonomy
        stage.status = "active"

    def complete(self, workflow_type: str, *, reason: str | None = None) -> None:
        stage = self._stage(workflow_type)
        self._ensure_running()
        if stage.status != "active":
            raise ValueError(f"stage {workflow_type!r} cannot complete from {stage.status!r}")
        stage.status = "completed"
        stage.reason = reason
        if all(current.status == "completed" for current in self._stages.values()):
            self.status = "completed"

    def fail(self, workflow_type: str, *, reason: str) -> None:
        stage = self._stage(workflow_type)
        self._ensure_running()
        if stage.status == "completed":
            raise ValueError(f"stage {workflow_type!r} cannot fail from {stage.status!r}")
        stage.status = "failed"
        stage.reason = reason
        self.status = "failed"
        self.failure = {
            "workflow_type": workflow_type,
            "reason": reason,
            "sensor_event_id": stage.sensor_event_id,
            "workflow_id": stage.workflow_id,
            "status": "failed",
        }

    def update_outcome(self, outcome: Mapping[str, Any]) -> None:
        if self.status not in {"running", "completed"}:
            raise ValueError("outcome can only be updated while running or after completion")
        self._outcome = deepcopy(dict(outcome))

    def view(self) -> dict[str, Any]:
        baseline = self._baseline or {}
        outcome = self._outcome or {}
        metric_keys = (*baseline, *(metric for metric in outcome if metric not in baseline))
        return {
            "id": self.id,
            "type": "trading-shock",
            "title": TITLE,
            "status": self.status,
            "trace_id": self.trace_id,
            "cause_event_id": self.cause_event_id,
            "started_at_sim_time": self.started_at_sim_time,
            "stages": [stage.view() for stage in self._stages.values()],
            "kpis": {
                metric: {
                    "before": deepcopy(baseline.get(metric)),
                    "after": deepcopy(outcome.get(metric)),
                }
                for metric in metric_keys
            },
            "failure": deepcopy(self.failure),
        }

    def stage(self, workflow_type: str) -> StoryStage:
        return replace(self._stage(workflow_type))

    def _stage(self, workflow_type: str) -> StoryStage:
        try:
            return self._stages[workflow_type]
        except KeyError as error:
            raise ValueError(f"unknown workflow_type {workflow_type!r}") from error

    def _ensure_running(self) -> None:
        if self.status != "running":
            raise ValueError(f"trading shock is not running: {self.status!r}")
