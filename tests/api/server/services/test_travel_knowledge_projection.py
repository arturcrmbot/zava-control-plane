"""RED-first proof for Task 7 Required A: a pack-owned Knowledge-graph
projection for Travel's ``flight-disruption-recovery`` workflow.

Registration point
-------------------
The projection is registered on ``VerticalPack.projections`` (Travel's own
generated manifest), never on the shared global
``api.server.services.entity_projections.PROJECTIONS`` dict directly —
that module-level dict is itself built from ``active_runtime().pack.projections``
at import time (see its own source), so registering on the pack IS the
correct, zero-global-edit registration mechanism. To stay immune to Python's
whole-process module-import-order/caching hazard (many verticals' tests share
one pytest process), every assertion below reads ``runtime.pack.projections``
directly and drives a real :class:`EntityReflector` constructed with an
explicit ``projections=`` override rather than depending on the ambient
``entity_projections.PROJECTIONS`` snapshot.

Evidence source
----------------
The projection consumes the *real* terminal Task-6 orchestration evidence —
``workflow.payload["evidence"]["output"]`` (the orchestrator's own
``_build_output()`` terminal dict, threaded through by the industry-neutral
``WorldWorkflowAdapter.decided(..., evidence=...)`` parameter this task adds)
plus ``workflow.payload["observation"]`` (the real trigger observation
already stored by ``WorldWorkflowAdapter.start()``) — never a fabricated
fixture-only summary. Every scenario below is driven exactly like
``test_world_bridge_travel_recovery_integration.py``: the real minute-180
autonomous sensor, the real Durable orchestrator generator (only the Durable
HTTP *transport* is faked), and the real generic ``POST
/api/exceptions/{id}/resolve`` operator route for HITL approval — never a
``/processes/*/run`` call or any direct workflow-start shortcut.

Before this task's capability exists, every test below fails: either
``runtime.pack.projections`` has no ``"flight-disruption-recovery"`` entry at
all (``AssertionError`` / ``KeyError``), or the workflow carries no
``payload["evidence"]`` yet (because ``WorldWorkflowAdapter.decided()`` does
not accept/store one), so the projection can never resolve booking, flight,
supplier or decision/command/evaluation node identities — a missing
capability, never a syntax error.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import respx

import api.server.routes.exceptions as exceptions_module
from api.server.routes.exceptions import _resolve_one
from api.server.services.entity_graph import EntityGraph
from api.server.services.entity_reflector import EntityReflector
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
    _GOLDEN_MEMBER_CUSTOMER_IDS,
    _GOLDEN_NEW_FLIGHT_ID,
    _GOLDEN_PARTY_ID,
    _install_fake_durable_host,
    _low_cost_disruption,
    _run_until,
)

WORKFLOW_TYPE = "flight-disruption-recovery"


# ---------------------------------------------------------------------------
# Harness: same real ActorWorldService / fake-Durable-transport-only pattern
# as the Task 6 integration test, extended with a real temp-file EntityGraph
# (Required C: "test a temp graph/store materialization", not a mock) and a
# real EntityReflector subscribed from the very start (so it naturally
# re-projects on every workflow lifecycle event exactly as production code
# does -- no test-only shortcut into private dispatch methods).
# ---------------------------------------------------------------------------


def _state_with_graph(tmp_path: Path, seed: int = 42) -> SimpleNamespace:
    bus = EventBus()
    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=Path("."))
    service = ActorWorldService.for_runtime(runtime, seed=seed, bus=bus)
    graph = EntityGraph(tmp_path / "graph.kuzu")
    state = SimpleNamespace(
        bus=bus,
        world_service=service,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        runtime=runtime,
        entities=graph,
        domain_memories={},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    # Explicit projections= override (the pack's own mapping) -- never the
    # ambient global PROJECTIONS snapshot -- so this test is immune to
    # whichever vertical's tests happened to import
    # api.server.services.entity_projections first in this pytest process.
    reflector = EntityReflector(
        state.bus, state.store, state.entities,
        projections=dict(runtime.pack.projections),
    )
    reflector.start()
    state.entity_reflector = reflector
    return state


async def _drive_golden_to_completion(state: SimpleNamespace) -> tuple[str, _FakeDurableHTTPHost]:
    """Drive the exact golden high-cost scenario
    (minute-180 FLT-ZV204 cancellation -> HITL approval -> completed) to
    completion, exactly mirroring
    ``test_golden_high_cost_disruption_requires_hitl_approval_then_completes_recovery``.
    Returns ``(workflow_id, host)``.
    """
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()
    original_app_state = exceptions_module.app_state
    exceptions_module.app_state = state
    try:
        with respx.mock(assert_all_called=False) as respx_mock:
            _install_fake_durable_host(host, respx_mock)
            state.world_service.scenario.run(180.0)
            state.world_service._publish_new()
            await asyncio.sleep(0)
            await asyncio.sleep(0)

            assert len(host.schedule_payloads) == 1
            workflow_id = host.schedule_payloads[0]["workflow_id"]

            workflow = await _run_until(state, workflow_id, {"awaiting_hitl", "completed", "failed"})
            assert workflow.status == "awaiting_hitl"
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
    return workflow_id, host


# ---------------------------------------------------------------------------
# A1. Registration: pack-owned, no global registry edit.
# ---------------------------------------------------------------------------


def test_travel_pack_registers_flight_disruption_recovery_projection(tmp_path: Path) -> None:
    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=Path("."))
    projection = runtime.pack.projections.get(WORKFLOW_TYPE)
    assert projection is not None, (
        "Travel's VerticalPack.projections must register a real "
        f"{WORKFLOW_TYPE!r} projection function -- none found"
    )
    assert callable(projection)


# ---------------------------------------------------------------------------
# A2. Truthful absence: no fabricated subgraph before real recovery evidence
# exists on the workflow.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projection_yields_nothing_before_recovery_evidence_exists(tmp_path: Path) -> None:
    state = _state_with_graph(tmp_path)
    bridge = WorldBridge(state)
    bridge.start()
    host = _FakeDurableHTTPHost()
    with respx.mock(assert_all_called=False) as respx_mock:
        _install_fake_durable_host(host, respx_mock)
        state.world_service.scenario.run(180.0)
        state.world_service._publish_new()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        workflow_id = host.schedule_payloads[0]["workflow_id"]
        workflow = await _run_until(state, workflow_id, {"awaiting_hitl", "completed", "failed"})
        assert workflow.status == "awaiting_hitl"

        projection = state.runtime.pack.projections[WORKFLOW_TYPE]
        ops = projection(workflow)
        assert ops == [], (
            "projection must truthfully report nothing while the workflow is "
            "still awaiting HITL approval (no completed command/evidence yet) "
            f"-- got {ops!r}"
        )

        # The real reflector (subscribed since state construction) must not
        # have materialised a recovery subgraph either -- no booking->new
        # flight replacement path can exist yet.
        rows = state.entities.query(
            "MATCH (b:Asset {id: $booking_id})-[:RELATED_ASSET]->(f:Asset) "
            "RETURN f.id AS id",
            {"booking_id": _GOLDEN_BOOKING_ID},
        )
        assert rows == []


# ---------------------------------------------------------------------------
# A3. Full recovery subgraph: exact node/edge identities from real evidence,
# before/after semantic delta, changed outcome visible.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projection_produces_full_recovery_subgraph_with_exact_golden_ids(tmp_path: Path) -> None:
    state = _state_with_graph(tmp_path)

    # -- BEFORE: fresh graph, no recovery subgraph of any kind -------------
    before_rows = state.entities.query(
        "MATCH (b:Asset {id: $booking_id})-[:RELATED_ASSET]->(f:Asset {id: $new_flight_id}) "
        "RETURN f.id AS id",
        {"booking_id": _GOLDEN_BOOKING_ID, "new_flight_id": _GOLDEN_NEW_FLIGHT_ID},
    )
    assert before_rows == [], "no booking->new-flight recovery edge should exist before completion"

    workflow_id, host = await _drive_golden_to_completion(state)
    instance = host.instances[
        state.store.get_workflow(workflow_id).orchestration_instance_id
    ]
    output = instance.output
    command = output["command"]
    cmd_payload = command["payload"]
    option_id = cmd_payload["option_id"]
    old_supplier_id = cmd_payload["old_supplier_id"]
    new_supplier_id = cmd_payload["new_supplier_id"]
    hotel_id = cmd_payload["hotel_id"]
    hotel_supplier_id = cmd_payload["hotel_supplier_id"]
    new_transfer_id = cmd_payload["new_transfer_id"]
    new_transfer_supplier_id = cmd_payload["new_transfer_supplier_id"]
    decision_id = cmd_payload["decision_id"]
    command_id = command["command_id"]
    evaluation_id = f"EVAL-{workflow_id}-{option_id}"

    # Give the bus-driven reflector a beat to finish reacting to the terminal
    # `decided`/`resolved` events (handlers run synchronously inside
    # `bus.emit`, but leave this here for robustness against any future
    # asynchronous dispatch change).
    await asyncio.sleep(0)

    # -- AFTER: exact changed-outcome edges now visible ---------------------
    replaced = state.entities.query(
        "MATCH (old:Asset {id: $old})-[r:RELATED_ASSET]->(new:Asset {id: $new}) "
        "RETURN r.role AS role",
        {"old": _GOLDEN_FLIGHT_ID, "new": _GOLDEN_NEW_FLIGHT_ID},
    )
    assert [r["role"] for r in replaced] == ["replaced_by"], (
        f"FLT-ZV204->FLT-ZV205 replacement relation must exist after projection, got {replaced!r}"
    )
    reaccommodated = state.entities.query(
        "MATCH (b:Asset {id: $booking})-[r:RELATED_ASSET]->(f:Asset {id: $flight}) "
        "RETURN r.role AS role",
        {"booking": _GOLDEN_BOOKING_ID, "flight": _GOLDEN_NEW_FLIGHT_ID},
    )
    assert [r["role"] for r in reaccommodated] == ["reaccommodated_on"], (
        f"booking must link to FLT-ZV205 after projection, got {reaccommodated!r}"
    )
    retained_hotel = state.entities.query(
        "MATCH (b:Asset {id: $booking})-[r:RELATED_ASSET]->(h:Asset {id: $hotel}) "
        "RETURN r.role AS role",
        {"booking": _GOLDEN_BOOKING_ID, "hotel": hotel_id},
    )
    assert [r["role"] for r in retained_hotel] == ["retained_hotel"], (
        f"booking must retain its hotel after projection, got {retained_hotel!r}"
    )
    assigned_transfer = state.entities.query(
        "MATCH (b:Asset {id: $booking})-[r:RELATED_ASSET]->(t:Asset {id: $transfer}) "
        "RETURN r.role AS role",
        {"booking": _GOLDEN_BOOKING_ID, "transfer": new_transfer_id},
    )
    assert [r["role"] for r in assigned_transfer] == ["assigned_transfer"], (
        f"booking must be assigned its new transfer after projection, got {assigned_transfer!r}"
    )

    # -- exact node identities -----------------------------------------------
    def _node_ids(kind: str) -> set[str]:
        rows = state.entities.query(f"MATCH (n:{kind}) RETURN n.id AS id")
        return {r["id"] for r in rows}

    assert workflow_id in _node_ids("Workflow")
    assert _GOLDEN_DISRUPTION_ID in _node_ids("Asset")
    assert _GOLDEN_BOOKING_ID in _node_ids("Asset")
    assert _GOLDEN_PARTY_ID in _node_ids("Asset")
    assert _GOLDEN_FLIGHT_ID in _node_ids("Asset")
    assert _GOLDEN_NEW_FLIGHT_ID in _node_ids("Asset")
    assert hotel_id in _node_ids("Asset")
    assert new_transfer_id in _node_ids("Asset")
    assert option_id in _node_ids("Asset")
    person_ids = _node_ids("Person")
    for cus_id in _GOLDEN_MEMBER_CUSTOMER_IDS:
        assert cus_id in person_ids
    org_ids = _node_ids("Organisation")
    assert old_supplier_id in org_ids
    assert new_supplier_id in org_ids
    assert hotel_supplier_id in org_ids
    assert new_transfer_supplier_id in org_ids
    decision_ids = _node_ids("Decision")
    assert decision_id in decision_ids
    assert command_id in decision_ids
    assert evaluation_id in decision_ids

    # -- exact relationship existence for every required verb ---------------
    def _rel_exists(src: str, rel: str, dst: str) -> bool:
        rows = state.entities.query(
            f"MATCH (a {{id: $src}})-[r:{rel}]->(b {{id: $dst}}) RETURN count(r) AS n",
            {"src": src, "dst": dst},
        )
        return bool(rows) and rows[0]["n"] > 0

    assert _rel_exists(workflow_id, "TRIGGERED_BY", _GOLDEN_DISRUPTION_ID)
    assert _rel_exists(workflow_id, "AFFECTS_ASSET", _GOLDEN_BOOKING_ID)
    for cus_id in _GOLDEN_MEMBER_CUSTOMER_IDS:
        assert _rel_exists(_GOLDEN_PARTY_ID, "ASSIGNED_TO", cus_id)
    assert _rel_exists(decision_id, "DECIDED_ASSET", option_id)  # SELECTED_OPTION
    assert _rel_exists(command_id, "APPROVED_BY", decision_id)
    assert _rel_exists(decision_id, "ISSUED_COMMAND", command_id)
    assert _rel_exists(command_id, "DECIDED_ASSET", _GOLDEN_BOOKING_ID)  # MUTATED
    assert _rel_exists(_GOLDEN_FLIGHT_ID, "SUPPLIED_BY_ASSET", old_supplier_id)
    assert _rel_exists(_GOLDEN_NEW_FLIGHT_ID, "SUPPLIED_BY_ASSET", new_supplier_id)
    assert _rel_exists(hotel_id, "SUPPLIED_BY_ASSET", hotel_supplier_id)
    assert _rel_exists(new_transfer_id, "SUPPLIED_BY_ASSET", new_transfer_supplier_id)
    assert _rel_exists(command_id, "EVALUATED_BY", evaluation_id)
    assert _rel_exists(evaluation_id, "RESOLVED_OBJECTIVE", workflow_id)


# ---------------------------------------------------------------------------
# A4. Transfer before/after delta: the old transfer must remain visible and
# explicitly point to the exact replacement, not merely leave a booking->new
# transfer assignment disconnected from the displaced leg.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projection_links_old_transfer_to_exact_replacement(tmp_path: Path) -> None:
    state = _state_with_graph(tmp_path)
    workflow_id, host = await _drive_golden_to_completion(state)
    command = host.instances[
        state.store.get_workflow(workflow_id).orchestration_instance_id
    ].output["command"]
    payload = command["payload"]
    old_transfer_id = payload["old_transfer_id"]
    new_transfer_id = payload["new_transfer_id"]

    old_transfer = state.entities.query(
        "MATCH (t:Asset {id: $id}) RETURN t.id AS id, t.kind AS kind",
        {"id": old_transfer_id},
    )
    assert old_transfer == [{"id": old_transfer_id, "kind": "transfer"}]
    replacement = state.entities.query(
        "MATCH (old:Asset {id: $old})-[r:RELATED_ASSET]->(new:Asset {id: $new}) "
        "RETURN r.role AS role",
        {"old": old_transfer_id, "new": new_transfer_id},
    )
    assert replacement == [{"role": "replaced_by"}]


# ---------------------------------------------------------------------------
# A5. Idempotency: re-running the projection produces no duplicate rows.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projection_second_application_is_idempotent(tmp_path: Path) -> None:
    state = _state_with_graph(tmp_path)
    workflow_id, _host = await _drive_golden_to_completion(state)
    await asyncio.sleep(0)

    def _counts() -> tuple[int, int]:
        # NOTE: Kuzu 0.6.1 mis-binds `RETURN count(n) AS n` (alias colliding
        # with the pattern variable name) as "Cannot evaluate expression with
        # type AGGREGATE_FUNCTION" -- always alias to a distinct name.
        node_rows = state.entities.query("MATCH (n:Asset) RETURN count(n) AS cnt")
        rel_rows = state.entities.query("MATCH ()-[r:RELATED_ASSET]->() RETURN count(r) AS cnt")
        return node_rows[0]["cnt"], rel_rows[0]["cnt"]

    first_node_count, first_rel_count = _counts()
    assert first_rel_count > 0, "sanity: at least one RELATED_ASSET edge must already exist"

    # Re-run the SAME projection function against the SAME completed workflow
    # a second time and re-apply the ops directly (bypassing the bus so the
    # re-application is deterministic and not timing-dependent).
    workflow = state.store.get_workflow(workflow_id)
    projection = state.runtime.pack.projections[WORKFLOW_TYPE]
    ops = projection(workflow)
    assert ops, "second projection run must still deterministically re-derive the same ops"
    from api.server.services.entity_graph import EntityWrite, RelWrite
    for op in ops:
        if isinstance(op, EntityWrite):
            state.entities.upsert(op)
        elif isinstance(op, RelWrite):
            state.entities.link(op.src_id, op.rel, op.dst_id, **op.attrs)

    second_node_count, second_rel_count = _counts()
    assert second_node_count == first_node_count, "idempotent re-projection must not duplicate Asset nodes"
    assert second_rel_count == first_rel_count, "idempotent re-projection must not duplicate RELATED_ASSET edges"


# ---------------------------------------------------------------------------
# A6. Low-cost/auto-approved path also projects (no HITL decision actor, but
# the decision/command/evaluation chain still resolves deterministically).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_projection_covers_low_cost_auto_approved_path(tmp_path: Path) -> None:
    state = _state_with_graph(tmp_path)
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

    await asyncio.sleep(0)
    workflow = state.store.get_workflow(workflow_id)
    projection = state.runtime.pack.projections[WORKFLOW_TYPE]
    ops = projection(workflow)
    assert ops, "auto-approved low-cost recovery must still project a full subgraph"
    decision_ids = {op.id for op in ops if op.__class__.__name__ == "EntityWrite" and op.kind == "Decision"}
    assert any(d.startswith(f"DEC-{workflow_id}-") for d in decision_ids)
    assert any(d.startswith(f"CMD-{workflow_id}-") for d in decision_ids)
    assert any(d.startswith(f"EVAL-{workflow_id}-") for d in decision_ids)
