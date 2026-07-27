from __future__ import annotations

from copy import deepcopy

import pytest

from verticals.fashion.trading_shock import STAGE_DEPENDENCIES
from verticals.fashion.trading_shock import TradingShockState


CAUSE_EVENT_ID = "event:viral-drop"
TRACE_ID = "fashion-trading-shock-42"


def _started_state(baseline: dict[str, object] | None = None) -> TradingShockState:
    state = TradingShockState(seed=42)
    state.start(
        cause_event_id=CAUSE_EVENT_ID,
        trace_id=TRACE_ID,
        sim_time=12.5,
        baseline={} if baseline is None else baseline,
    )
    return state


def _drive_stage(
    state: TradingShockState,
    workflow_type: str,
    *,
    sensor_event_id: str,
    workflow_id: str,
    autonomy: str | None = None,
) -> None:
    state.mark_triggered(workflow_type, sensor_event_id=sensor_event_id)
    state.bind_workflow(workflow_type, workflow_id=workflow_id, autonomy=autonomy)
    state.complete(workflow_type)


def test_stage_dependencies_and_root_stages_are_deterministic() -> None:
    assert tuple(STAGE_DEPENDENCIES) == (
        "demand-spike-response",
        "inventory-rebalancing",
        "promotion-readiness",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
        "fulfilment-exception-resolution",
        "markdown-governance",
        "returns-disposition",
    )

    state = TradingShockState(seed=7)
    assert state.ready_to_trigger() == ()

    state.start(CAUSE_EVENT_ID, TRACE_ID, 12.5, baseline={"kpis": {"before": 1}})
    assert tuple(stage.workflow_type for stage in state.ready_to_trigger()) == (
        "demand-spike-response",
        "inventory-rebalancing",
    )


def test_dependency_unlocks_and_triggered_stages_are_visible_in_order() -> None:
    state = _started_state()

    _drive_stage(
        state,
        "demand-spike-response",
        sensor_event_id="sensor:demand",
        workflow_id="wf-demand",
    )

    assert tuple(stage.workflow_type for stage in state.ready_to_trigger()) == (
        "inventory-rebalancing",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
    )

    _drive_stage(
        state,
        "inventory-rebalancing",
        sensor_event_id="sensor:inventory",
        workflow_id="wf-inventory",
        autonomy="human-approved",
    )

    assert tuple(stage.workflow_type for stage in state.ready_to_trigger()) == (
        "promotion-readiness",
        "supplier-delay-recovery",
        "marketplace-seller-exception",
        "markdown-governance",
    )


def test_workflow_binding_sets_id_and_can_change_autonomy_label() -> None:
    state = _started_state()

    state.mark_triggered(
        "inventory-rebalancing",
        sensor_event_id="sensor:inventory",
    )
    stage = state.stage("inventory-rebalancing")
    assert stage.status == "triggered"
    assert stage.autonomy == "policy-safe"

    state.bind_workflow(
        "inventory-rebalancing",
        workflow_id="wf-inventory",
        autonomy="human-approved",
    )

    refreshed_stage = state.stage("inventory-rebalancing")
    assert refreshed_stage.status == "active"
    assert refreshed_stage.workflow_id == "wf-inventory"
    assert refreshed_stage.autonomy == "human-approved"

    stage.status = "failed"
    stage.sensor_event_id = "sensor:changed"
    stage.workflow_id = "wf-changed"

    untouched_stage = state.stage("inventory-rebalancing")
    assert untouched_stage.status == "active"
    assert untouched_stage.sensor_event_id == "sensor:inventory"
    assert untouched_stage.workflow_id == "wf-inventory"
def test_view_projects_stable_story_id_trace_and_per_metric_kpis() -> None:
    baseline = {
        "sell_through": {"percentage": 0.41, "bands": [10, 20]},
        "availability_pct": 0.51,
    }
    state = _started_state(baseline=baseline)
    state.update_outcome({
        "sell_through": {"percentage": 0.63, "bands": [15, 25]},
        "recovery_value_gbp": 1200.0,
    })
    baseline["sell_through"]["bands"].append(30)

    view = state.view()

    assert view == {
        "id": TRACE_ID,
        "type": "trading-shock",
        "title": "The viral summer drop",
        "status": "running",
        "trace_id": TRACE_ID,
        "cause_event_id": CAUSE_EVENT_ID,
        "started_at_sim_time": 12.5,
        "stages": [
            {
                "workflow_type": "demand-spike-response",
                "dependency_ids": [],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "policy-safe",
                "reason": None,
            },
            {
                "workflow_type": "inventory-rebalancing",
                "dependency_ids": [],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "policy-safe",
                "reason": None,
            },
            {
                "workflow_type": "promotion-readiness",
                "dependency_ids": [
                    "demand-spike-response",
                    "inventory-rebalancing",
                ],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
            {
                "workflow_type": "supplier-delay-recovery",
                "dependency_ids": ["demand-spike-response"],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
            {
                "workflow_type": "marketplace-seller-exception",
                "dependency_ids": ["demand-spike-response"],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
            {
                "workflow_type": "fulfilment-exception-resolution",
                "dependency_ids": [
                    "inventory-rebalancing",
                    "supplier-delay-recovery",
                    "marketplace-seller-exception",
                ],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
            {
                "workflow_type": "markdown-governance",
                "dependency_ids": ["inventory-rebalancing"],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
            {
                "workflow_type": "returns-disposition",
                "dependency_ids": [
                    "promotion-readiness",
                    "fulfilment-exception-resolution",
                ],
                "status": "waiting",
                "sensor_event_id": None,
                "workflow_id": None,
                "autonomy": "human-approved",
                "reason": None,
            },
        ],
        "kpis": {
            "sell_through": {
                "before": {"percentage": 0.41, "bands": [10, 20]},
                "after": {"percentage": 0.63, "bands": [15, 25]},
            },
            "availability_pct": {"before": 0.51, "after": None},
            "recovery_value_gbp": {"before": None, "after": 1200.0},
        },
        "failure": None,
    }


def test_completion_only_happens_after_all_eight_stages() -> None:
    state = _started_state()

    sequence = [
        ("demand-spike-response", "sensor:demand", "wf-demand"),
        ("inventory-rebalancing", "sensor:inventory", "wf-inventory"),
        ("promotion-readiness", "sensor:promotion", "wf-promotion"),
        ("supplier-delay-recovery", "sensor:supplier", "wf-supplier"),
        ("marketplace-seller-exception", "sensor:marketplace", "wf-marketplace"),
        ("fulfilment-exception-resolution", "sensor:fulfilment", "wf-fulfilment"),
        ("markdown-governance", "sensor:markdown", "wf-markdown"),
        ("returns-disposition", "sensor:returns", "wf-returns"),
    ]

    for index, (workflow_type, sensor_event_id, workflow_id) in enumerate(sequence, start=1):
        state.mark_triggered(workflow_type, sensor_event_id=sensor_event_id)
        state.bind_workflow(workflow_type, workflow_id=workflow_id)
        state.complete(workflow_type)
        if index < len(sequence):
            assert state.status == "running"

    assert state.status == "completed"
    assert state.ready_to_trigger() == ()


def test_failure_stops_dependants_and_records_failure_details() -> None:
    state = _started_state()

    state.mark_triggered("demand-spike-response", sensor_event_id="sensor:demand")
    state.bind_workflow("demand-spike-response", workflow_id="wf-demand")
    state.fail("demand-spike-response", reason="supplier outage")

    assert state.status == "failed"
    assert state.ready_to_trigger() == ()
    assert state.view()["failure"] == {
        "workflow_type": "demand-spike-response",
        "reason": "supplier outage",
        "sensor_event_id": "sensor:demand",
        "workflow_id": "wf-demand",
        "status": "failed",
    }


def test_fail_rejects_completed_and_already_failed_stages() -> None:
    completed_state = _started_state()
    completed_state.mark_triggered("demand-spike-response", sensor_event_id="sensor:demand")
    completed_state.bind_workflow("demand-spike-response", workflow_id="wf-demand")
    completed_state.complete("demand-spike-response")

    with pytest.raises(ValueError):
        completed_state.fail("demand-spike-response", reason="too late")

    failed_state = _started_state()
    failed_state.mark_triggered("inventory-rebalancing", sensor_event_id="sensor:inventory")
    failed_state.bind_workflow("inventory-rebalancing", workflow_id="wf-inventory")
    failed_state.fail("inventory-rebalancing", reason="already failed")

    with pytest.raises(ValueError):
        failed_state.fail("inventory-rebalancing", reason="already failed")


def test_bind_workflow_is_idempotent_for_same_workflow_id_while_active() -> None:
    state = _started_state()
    state.mark_triggered("inventory-rebalancing", sensor_event_id="sensor:inventory")

    state.bind_workflow("inventory-rebalancing", workflow_id="wf-inventory")
    state.bind_workflow(
        "inventory-rebalancing",
        workflow_id="wf-inventory",
        autonomy="human-approved",
    )

    stage = state.stage("inventory-rebalancing")
    assert stage.status == "active"
    assert stage.workflow_id == "wf-inventory"
    assert stage.autonomy == "human-approved"

    with pytest.raises(ValueError):
        state.bind_workflow("inventory-rebalancing", workflow_id="wf-inventory-2")


def test_update_outcome_rejects_before_start_and_after_story_failure() -> None:
    state = TradingShockState(seed=42)

    with pytest.raises(ValueError):
        state.update_outcome({"sell_through": 0.5})

    running_state = _started_state()
    running_state.mark_triggered("demand-spike-response", sensor_event_id="sensor:demand")
    running_state.bind_workflow("demand-spike-response", workflow_id="wf-demand")
    running_state.fail("demand-spike-response", reason="supplier outage")

    with pytest.raises(ValueError):
        running_state.update_outcome({"sell_through": 0.6})


def test_unknown_and_illegal_transitions_are_rejected() -> None:
    state = _started_state()

    with pytest.raises(ValueError):
        state.stage("does-not-exist")

    with pytest.raises(ValueError):
        state.mark_triggered("does-not-exist", sensor_event_id="sensor:unknown")

    with pytest.raises(ValueError):
        state.complete("demand-spike-response")

    state.mark_triggered("demand-spike-response", sensor_event_id="sensor:demand")
    state.bind_workflow("demand-spike-response", workflow_id="wf-demand")
    state.complete("demand-spike-response")

    with pytest.raises(ValueError):
        state.bind_workflow("demand-spike-response", workflow_id="wf-again")

    with pytest.raises(ValueError):
        state.mark_triggered("demand-spike-response", sensor_event_id="sensor:again")


def test_start_copies_baseline_and_view_reuses_the_copy() -> None:
    baseline = {
        "inventory": {
            "sell_through": 0.51,
            "bands": [1, 2, 3],
        }
    }
    state = _started_state(baseline=baseline)
    copied_before = deepcopy(baseline)

    baseline["inventory"]["bands"].append(4)
    state.update_outcome({"inventory": {"sell_through": 0.73, "bands": [5, 6]}})

    view = state.view()
    assert view["kpis"] == {
        "inventory": {
            "before": copied_before["inventory"],
            "after": {"sell_through": 0.73, "bands": [5, 6]},
        },
    }


def test_ready_to_trigger_returns_defensive_stage_snapshots() -> None:
    state = _started_state()

    ready_stage = state.ready_to_trigger()[0]
    ready_stage.status = "failed"
    ready_stage.sensor_event_id = "sensor:mutated"

    assert state.stage(ready_stage.workflow_type).status == "waiting"
    assert state.stage(ready_stage.workflow_type).sensor_event_id is None
    assert ready_stage.workflow_type in {
        stage.workflow_type for stage in state.ready_to_trigger()
    }
