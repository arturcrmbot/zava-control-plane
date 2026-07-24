"""RED-first proof for Task 7 Required B: an exact workflow-detail payload
for Travel's ``flight-disruption-recovery`` workflow, retrieved through the
existing, industry-neutral ``GET /api/workflows/{id}`` route -- never a new
Travel-specific route.

The automatically-created workflow id used below always comes from the real
bridge's own ``host.schedule_payloads[0]["workflow_id"]`` (or the canonical
``StateStore``), never a hardcoded/heuristic/"latest" guess -- proving the
"exact workflow drill-in by auto-fired ID" requirement structurally, not just
by assertion.

Mechanism
---------
``api.server.routes.workflows.get_workflow`` is called directly (mirroring
how the Task 6 integration test calls ``_resolve_one`` directly rather than
spinning up a FastAPI ``TestClient``), with the route module's *module-level*
``app_state`` temporarily monkeypatched onto this test's own lightweight
``SimpleNamespace`` state -- the same established idiom
``test_world_bridge_travel_recovery_integration.py`` already uses for
``api.server.routes.exceptions.app_state``. This test never imports or calls
any ``/processes/*/run`` route or direct workflow-start endpoint; the ONLY
trigger for every scenario below is the real minute-180 autonomous sensor
(golden) or a hand-built low-cost disruption against the same live
``ActorWorldService.scenario`` (mirroring
``test_travel_recovery_functions.py``'s own low-cost mechanics), exactly like
``test_world_bridge_travel_recovery_integration.py``.

Before this task's capability exists, every test below fails: the route's
response carries no pack-contributed detail at all (``VerticalPack`` has no
``workflow_detail_hook`` field yet, and even if it did, nothing populates
``workflow.payload["evidence"]`` for the hook to read) -- a missing
capability, never a syntax/import error.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import respx

import api.server.routes.exceptions as exceptions_module
import api.server.routes.workflows as workflows_module
from api.server.routes.exceptions import _resolve_one
from api.server.routes.workflows import get_workflow
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime
from tests.api.server.services.test_world_bridge_travel_recovery_integration import (
    _FakeDurableHTTPHost,
    _GOLDEN_BOOKING_ID,
    _GOLDEN_DISRUPTION_ID,
    _GOLDEN_FLIGHT_ID,
    _GOLDEN_INCREMENTAL_COST_GBP,
    _GOLDEN_MEMBER_CUSTOMER_IDS,
    _GOLDEN_NEW_FLIGHT_ID,
    _GOLDEN_PARTY_ID,
    _install_fake_durable_host,
    _low_cost_disruption,
    _run_until,
)

pytestmark = pytest.mark.asyncio


def _travel_state(seed: int = 42) -> SimpleNamespace:
    bus = EventBus()
    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=Path("."))
    service = ActorWorldService.for_runtime(runtime, seed=seed, bus=bus)
    state = SimpleNamespace(
        bus=bus,
        world_service=service,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        runtime=runtime,
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state


async def _get_detail(state: SimpleNamespace, workflow_id: str) -> dict:
    """Call the real, unmodified `GET /api/workflows/{id}` handler directly
    against `state`, exactly mirroring the established
    `exceptions_module.app_state = state` monkeypatch idiom."""
    original = workflows_module.app_state
    workflows_module.app_state = state
    try:
        return await get_workflow(workflow_id)
    finally:
        workflows_module.app_state = original


async def _drive_golden_to_awaiting_hitl(state: SimpleNamespace):
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()
    respx_mock = respx.mock(assert_all_called=False)
    respx_mock.start()
    _install_fake_durable_host(host, respx_mock)
    state.world_service.scenario.run(180.0)
    state.world_service._publish_new()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    workflow_id = host.schedule_payloads[0]["workflow_id"]
    workflow = await _run_until(state, workflow_id, {"awaiting_hitl", "completed", "failed"})
    assert workflow.status == "awaiting_hitl"
    return workflow_id, host, respx_mock


async def _drive_golden_to_completion(state: SimpleNamespace) -> tuple[str, _FakeDurableHTTPHost]:
    workflow_id, host, respx_mock = await _drive_golden_to_awaiting_hitl(state)
    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        exception = next(
            e for e in state.store.list_exceptions(include_resolved=False)
            if e.workflow_id == workflow_id
        )
        approved = await _resolve_one(exception.id, "approve", "head_of_operations")
        assert approved is True
        workflow = await _run_until(state, workflow_id, {"completed", "failed"})
        assert workflow.status == "completed"
    finally:
        exceptions_module.app_state = original_app_state
        respx_mock.stop()
    return workflow_id, host


async def _drive_low_cost_to_completion(state: SimpleNamespace) -> tuple[str, _FakeDurableHTTPHost]:
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()
    with respx.mock(assert_all_called=False) as respx_mock:
        _install_fake_durable_host(host, respx_mock)
        _low_cost_disruption(state)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        workflow_id = host.schedule_payloads[0]["workflow_id"]
        workflow = await _run_until(state, workflow_id, {"completed", "failed"})
        assert workflow.status == "completed"
    return workflow_id, host


# ---------------------------------------------------------------------------
# B1. Missing/partial evidence fails clearly -- no success-shaped defaults.
# ---------------------------------------------------------------------------


async def test_workflow_detail_truthfully_absent_while_awaiting_hitl() -> None:
    state = _travel_state()
    workflow_id, _host, respx_mock = await _drive_golden_to_awaiting_hitl(state)
    try:
        detail = await _get_detail(state, workflow_id)
    finally:
        respx_mock.stop()
    pack_detail = detail.get("packDetail")
    assert pack_detail is not None, "packDetail must be present (even if it reports absence), never silently omitted"
    assert pack_detail.get("command") is None, (
        "no reaccommodate_travellers command exists yet while awaiting HITL -- "
        "must be truthfully absent, not fabricated"
    )
    assert not pack_detail.get("evaluation") or pack_detail["evaluation"].get("status") in (None, "not_applicable"), (
        "no evaluation can exist before a command has even been authorised"
    )


# ---------------------------------------------------------------------------
# B2. High-cost golden path: complete evidence contract.
# ---------------------------------------------------------------------------


async def test_workflow_detail_high_cost_path_has_complete_evidence_contract() -> None:
    state = _travel_state()
    workflow_id, host = await _drive_golden_to_completion(state)
    detail = await _get_detail(state, workflow_id)
    pack_detail = detail["packDetail"]

    # -- trigger evidence -----------------------------------------------
    trigger = pack_detail["trigger"]
    assert trigger["disruption_id"] == _GOLDEN_DISRUPTION_ID
    assert trigger["flight_id"] == _GOLDEN_FLIGHT_ID
    assert trigger["booking_id"] == _GOLDEN_BOOKING_ID
    assert trigger["party_id"] == _GOLDEN_PARTY_ID
    assert set(_GOLDEN_MEMBER_CUSTOMER_IDS).issubset(set(trigger["member_customer_ids"]))
    assert trigger["hotel_id"]
    assert trigger.get("sensor_id")
    assert trigger.get("evidence_event_ids")

    # -- ordered phase records --------------------------------------------
    phases = pack_detail["phases"]
    assert [p["name"] for p in phases] == [
        "detect", "assess_impact", "search_alternatives", "bound_options",
        "approve_material_change", "reaccommodate", "notify", "evaluate",
    ]
    for phase in phases:
        assert phase["status"], f"phase {phase['name']!r} must carry a truthful status"
        assert "evidence" in phase

    # -- pack skill/tool names ----------------------------------------------
    assert "operations_controller" in pack_detail["skills"]
    assert "head_of_operations" in pack_detail["skills"]
    assert any("reaccommodate" in t for t in pack_detail["tools"])

    # -- inspectable reasoning: <=3 alternatives, ranking/capacity/cost -----
    reasoning = pack_detail["reasoning"]
    assert reasoning["affected_analysis"]
    alternatives = reasoning["alternatives"]
    assert 1 <= len(alternatives) <= 3
    for alt in alternatives:
        assert alt["option_id"]
        assert "incremental_cost_gbp" in alt
        assert "material_changes" in alt
        assert "capacity_evidence" in alt
    assert reasoning["selected_option"]
    assert reasoning["authority_rule"]

    # -- HITL: required, deterministic ids, role, actor/outcome -------------
    hitl = pack_detail["hitl"]
    assert hitl["required"] is True
    assert hitl["gate_id"] == workflow_id
    assert hitl["decision_id"] == f"DEC-{workflow_id}-{reasoning['selected_option']}"
    assert hitl["required_role"] == "head_of_operations"
    assert hitl["decision_actor"] == "head_of_operations"
    assert hitl["outcome"] == "approved"

    # -- typed reaccommodate_travellers command: exact ids ------------------
    command = pack_detail["command"]
    assert command["type"] == "reaccommodate_travellers"
    assert command["option_id"] == reasoning["selected_option"]
    assert command["booking_id"] == _GOLDEN_BOOKING_ID
    assert command["old_flight_id"] == _GOLDEN_FLIGHT_ID
    assert command["new_flight_id"] == _GOLDEN_NEW_FLIGHT_ID
    assert command["incremental_cost_gbp"] == _GOLDEN_INCREMENTAL_COST_GBP
    assert command["command_id"] == f"CMD-{workflow_id}-{reasoning['selected_option']}"
    assert set(_GOLDEN_MEMBER_CUSTOMER_IDS).issubset(set(command["traveller_ids"]))
    assert command["old_supplier_id"]
    assert command["new_supplier_id"]

    # -- terminal evaluation + objective -------------------------------------
    evaluation = pack_detail["evaluation"]
    assert evaluation["evaluation_id"] == f"EVAL-{workflow_id}-{reasoning['selected_option']}"
    assert evaluation["status"] == "pass"
    assert evaluation.get("criteria")
    objective = pack_detail["objective"]
    assert objective["objective_id"]
    assert objective["status"] == "resolved"

    # -- exact Durable identity ------------------------------------------
    durable = pack_detail["durable"]
    assert durable["workflow_id"] == workflow_id
    assert durable["orchestration_instance_id"] in host.instances
    assert durable.get("trace_id")


# ---------------------------------------------------------------------------
# B3. Low-cost path: HITL truthfully marked N/A, not fabricated as approved.
# ---------------------------------------------------------------------------


async def test_workflow_detail_low_cost_path_marks_hitl_not_applicable() -> None:
    state = _travel_state()
    workflow_id, _host = await _drive_low_cost_to_completion(state)
    detail = await _get_detail(state, workflow_id)
    pack_detail = detail["packDetail"]

    hitl = pack_detail["hitl"]
    assert hitl["required"] is False
    assert hitl["gate_id"] is None, "no HITL gate was ever created for the auto-approved branch"
    assert hitl["required_role"] is None
    # A decision still genuinely exists (auto-approval), so its outcome is
    # truthfully reported -- this is NOT the same claim as "HITL occurred".
    assert pack_detail["command"] is not None
    assert pack_detail["command"]["decision_outcome"] == "auto_approved"
    evaluation = pack_detail["evaluation"]
    assert evaluation["status"] == "pass"


# ---------------------------------------------------------------------------
# B4. Exact drill-in by auto-fired ID, never a latest/first heuristic.
# ---------------------------------------------------------------------------


async def test_workflow_detail_drill_in_targets_exact_id_not_latest() -> None:
    # Both workflows are driven against the SAME state/store so drill-in can
    # be proven against a store that genuinely holds >1 workflow. The
    # low-cost scenario must run first: it advances the shared simulation
    # clock only to minute 90, and `SimulationRuntime.run_until` refuses to
    # run backwards, so the golden (minute-180) scenario must come second.
    state = _travel_state()
    low_cost_id, _host2 = await _drive_low_cost_to_completion(state)
    golden_id, _host1 = await _drive_golden_to_completion(state)
    assert golden_id != low_cost_id

    golden_detail = (await _get_detail(state, golden_id))["packDetail"]
    low_cost_detail = (await _get_detail(state, low_cost_id))["packDetail"]

    assert golden_detail["durable"]["workflow_id"] == golden_id
    assert golden_detail["trigger"]["booking_id"] == _GOLDEN_BOOKING_ID
    assert low_cost_detail["durable"]["workflow_id"] == low_cost_id
    assert low_cost_detail["trigger"]["booking_id"] != _GOLDEN_BOOKING_ID
    # Drilling into the golden id must never silently return the other
    # workflow's (e.g. most-recently-created) detail.
    assert golden_detail["command"]["booking_id"] == _GOLDEN_BOOKING_ID
