"""RED-first proof for Task 7 quality/completeness issue #3: the real
autonomous Travel ``flight-disruption-recovery`` resolved path must capture
operational Memory carrying the EXACT full workflow id, outcome and actor
ids -- never declared "Memory N/A", and never proven only at the
adapter-level with a hand-built, synthetic ``outcome`` dict (see the
pre-existing ``test_resolved_captures_truthful_operational_memory`` in
``test_world_workflow_adapter.py``, which asserts only
``memory.add.assert_called_once()`` against a network-incident domain with a
hand-crafted ``{"status": "resolved", "evidence_event_type": "site.recovered"}``
-- never the real, industry-neutral ``Evaluation.to_dict()`` shape a genuine
autonomous recovery actually produces, and never Travel at all).

This file drives the exact same real minute-180 FLT-ZV204 golden scenario as
``test_world_bridge_travel_recovery_integration.py`` (real ``ActorWorldService``,
real Durable orchestrator generator, only the Durable HTTP *transport* faked,
real generic ``POST /api/exceptions/{id}/resolve`` HITL approval -- never a
``/processes/*/run`` route or any direct workflow-start shortcut) through to
``"completed"``, with a real ``domain_memories["flight-disruption-recovery"]``
double wired in from the start. It then proves the captured record's
``extra_metadata`` carries the exact full workflow id, workflow_type,
workflow_status, trace id, ``BKG-4``, ``CUS-8``/``CUS-9``, decision id,
command id and the ``"reaccommodated"``/``"completed"`` outcome -- structural
equality against the real Durable instance output and workflow payload, not
fuzzy text matching. A dedicated ``_RecordingDomainMemory.search`` performs
deliberately EXACT (non-fuzzy) substring matching, so this file can also
directly disprove that a near-prefix/wildcard query (e.g. ``"BKG-4" + "0"``)
would count as exact-match proof.

Before issue #3's adapter enhancement exists, this test fails: the current
``_capture_operational_memory`` only ever serializes ``workflow.id`` and
``trace_id`` into free text, plus an ``evidence_event_type`` key that the
real ``Evaluation.to_dict()`` outcome never actually carries (it always
falls back to the literal string ``"world evidence"``) -- so
``extra_metadata`` carries none of workflow_type/workflow_status/evidence/
observation/outcome, and the required booking/customer/decision/command ids
are entirely absent from both the structural assertions and the haystack
substring checks below. A missing capability, never a syntax error.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import respx

import api.server.routes.exceptions as exceptions_module
from api.server.routes.exceptions import _resolve_one
from api.server.services.event_bus import EventBus
from api.server.services.state_store import StateStore
from api.server.services.workflow_event_ingestor import WorkflowEventIngestor
from api.server.services.world_bridge import WorldBridge
from api.server.world.service import ActorWorldService
from api.shared.vertical_loader import build_runtime
from tests.api.server.services.test_world_bridge_travel_recovery_integration import (
    _FakeDurableHTTPHost,
    _GOLDEN_BOOKING_ID,
    _GOLDEN_MEMBER_CUSTOMER_IDS,
    _install_fake_durable_host,
    _run_until,
)

WORKFLOW_TYPE = "flight-disruption-recovery"


# ---------------------------------------------------------------------------
# Recording double: proves exactly what the adapter wrote (never just "was
# called"), and provides a real, deliberately EXACT (non-fuzzy) substring
# `search` so "a near-prefix/wildcard query does not count as exact-match
# proof" can be demonstrated directly rather than merely asserted in prose.
# ---------------------------------------------------------------------------


class _RecordingDomainMemory:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def add(self, text, *, agent_skill="", workflow_id="", kind="working", extra_metadata=None):
        self.calls.append({
            "text": text,
            "agent_skill": agent_skill,
            "workflow_id": workflow_id,
            "kind": kind,
            "extra_metadata": extra_metadata or {},
        })

    @staticmethod
    def _haystack(record: dict) -> str:
        return record["text"] + " " + json.dumps(record["extra_metadata"], sort_keys=True, default=str)

    def search(self, query: str) -> list[dict]:
        """Deliberately EXACT substring search over every captured record --
        never a fuzzy/prefix/wildcard match -- so a caller can tell a real
        exact-id hit apart from a merely-similar near-miss."""
        return [call for call in self.calls if query in self._haystack(call)]


# ---------------------------------------------------------------------------
# Harness: same real ActorWorldService / fake-Durable-transport-only pattern
# as the Task 6 integration test and `test_travel_knowledge_projection.py`,
# with a real `domain_memories["flight-disruption-recovery"]` wired in from
# construction instead of an EntityGraph.
# ---------------------------------------------------------------------------


def _state_with_memory(seed: int = 42) -> tuple[SimpleNamespace, _RecordingDomainMemory]:
    bus = EventBus()
    runtime = build_runtime({"ZAVA_VERTICAL": "travel"}, data_root=Path("."))
    service = ActorWorldService.for_runtime(runtime, seed=seed, bus=bus)
    memory = _RecordingDomainMemory()
    state = SimpleNamespace(
        bus=bus,
        world_service=service,
        world_last_response=None,
        store=StateStore(),
        hub=MagicMock(),
        audit=MagicMock(),
        orchestration_history={},
        runtime=runtime,
        domain_memories={WORKFLOW_TYPE: memory},
    )
    state.workflow_event_ingestor = WorkflowEventIngestor(state)
    return state, memory


async def _drive_golden_to_completion(state: SimpleNamespace) -> tuple[str, _FakeDurableHTTPHost]:
    """Drive the exact golden high-cost scenario (minute-180 FLT-ZV204
    cancellation -> HITL approval -> completed) to completion, exactly
    mirroring
    ``test_golden_high_cost_disruption_requires_hitl_approval_then_completes_recovery``
    and ``test_travel_knowledge_projection.py``'s own
    ``_drive_golden_to_completion``. Returns ``(workflow_id, host)``.
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


@pytest.mark.asyncio
async def test_real_autonomous_travel_recovery_captures_operational_memory_with_exact_ids():
    state, memory = _state_with_memory()
    workflow_id, host = await _drive_golden_to_completion(state)

    assert len(memory.calls) == 1, (
        "the real autonomous resolved path must write exactly one operational "
        f"memory record -- got {len(memory.calls)}"
    )
    record = memory.calls[0]
    assert record["workflow_id"] == workflow_id

    workflow = state.store.get_workflow(workflow_id)
    instance = host.instances[workflow.orchestration_instance_id]
    output = instance.output
    command = output["command"]
    decision_id = command["payload"]["decision_id"]
    command_id = command["command_id"]
    trace_id = output["trace_id"]

    # -- exact structural proof: real ids, not fuzzy text matching ----------
    metadata = record["extra_metadata"]
    assert metadata["workflow_type"] == WORKFLOW_TYPE
    assert metadata["workflow_status"] == "completed"
    assert metadata["evidence"]["workflow_id"] == workflow_id
    assert metadata["evidence"]["booking_id"] == _GOLDEN_BOOKING_ID
    assert metadata["evidence"]["command"]["command_id"] == command_id
    assert metadata["evidence"]["command"]["payload"]["decision_id"] == decision_id
    assert (
        metadata["evidence"]["evaluation_intent"]["expected_success_event_type"]
        == "booking.reaccommodated"
    )
    assert metadata["observation"]["member_customer_ids"] == list(_GOLDEN_MEMBER_CUSTOMER_IDS)
    assert metadata["outcome"]["command_id"] == command_id
    assert metadata["outcome"]["trace_id"] == trace_id
    assert metadata["outcome"]["status"] == "resolved"

    # -- every required id/outcome substring genuinely present in the
    # combined narrative + metadata haystack ---------------------------------
    haystack = memory._haystack(record)
    for required in (
        workflow_id, WORKFLOW_TYPE, trace_id, _GOLDEN_BOOKING_ID,
        *_GOLDEN_MEMBER_CUSTOMER_IDS, decision_id, command_id,
        "completed", "reaccommodated",
    ):
        assert required in haystack, f"{required!r} missing from captured operational memory"

    # -- "a near-prefix/wildcard query does not count as exact-match proof":
    # the real ids hit; a merely-similar near-miss (same prefix, extra digit)
    # must NOT. -----------------------------------------------------------
    assert memory.search(workflow_id) != []
    assert memory.search(workflow_id + "0") == [], (
        "a near-prefix workflow id must not spuriously match"
    )
    assert memory.search(workflow_id + "*") == [], (
        "a wildcard-like workflow id must not spuriously match"
    )
    assert memory.search(_GOLDEN_BOOKING_ID) != []
    assert memory.search(_GOLDEN_BOOKING_ID + "0") == [], (
        "a near-prefix query must not spuriously match -- proves the id was "
        "captured exactly, not merely as a loose prefix"
    )
    assert memory.search(command_id) != []
    assert memory.search(command_id + "-wildcard") == []
    for cus_id in _GOLDEN_MEMBER_CUSTOMER_IDS:
        assert memory.search(cus_id) != []
        assert memory.search(cus_id + "0") == []
