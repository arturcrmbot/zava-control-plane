"""Phase 3 — Implementation Phase 8 (TASK-044).

End-to-end smoke proving the function-FMs substrate is live:

* 9 per-non-legacy-function FleetManagers constructed at boot;
* AmbientDispatcher subscribed + the three concrete ambient agents
  (``budget-variance-watcher``, ``vendor-risk-watcher``,
  ``access-anomaly-watcher``) discovered at import time;
* per-function SSE topics registered on the shared ``SSEHub``;
* AccessAnomalyWatcher's BusTrigger fires on a synthetic
  ``workflow.completed`` event for an approved ``it-access-request``
  → spawns ``access-review``;
* VendorRiskWatcher's CypherTrigger sweep fires when a high-risk
  vendor is seeded into the entity graph → spawns ``vendor-kyc``
  re-screen.

The plan's TASK-044 (live ``./scripts/profile-autonomous.sh`` smoke
with HTTP assertions) is **not** runnable in CI — it requires a long-
running uvicorn + autonomous profiler and would race the dispatcher's
real spawn integration that lands in Phase 4. This in-process smoke
is the executable proxy for that gate; the live run is documented in
the plan's IP8 acceptance command block and remains a developer-local
sign-off step.
"""
from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import pytest

from api.shared.events import FleetEvent


# ---------------------------------------------------------------------------
# Helper — mirror tests/api/server/test_appstate_entity_wiring.py
# ---------------------------------------------------------------------------


async def _build_app_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Construct a fresh ``AppState`` rooted at ``tmp_path``.

    Reloads ``api.server.state`` so the module-level singleton + its
    kuzu file lock are pinned to the per-test temp dir, then closes
    the singleton built at reload time so its kuzu file lock doesn't
    collide with the AppState we hand back to the test.
    """
    monkeypatch.setenv("PORTAL_DATA_DIR", str(tmp_path))
    import api.server.state as state_mod
    importlib.reload(state_mod)
    await state_mod.app_state.aclose()

    state = state_mod.AppState()
    # ``init_function_fms`` is called by the module bottom under
    # normal import, but our reload + manual AppState() construction
    # bypassed that. Drive it explicitly so function_fms + the
    # AmbientDispatcher are wired the same way main.py does at boot.
    state.init_function_fms()
    return state


# ---------------------------------------------------------------------------
# TASK-044 #1 — substrate alive
# ---------------------------------------------------------------------------


async def test_phase_3_substrate_has_function_fms_and_ambient_dispatcher_alive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Phase 3 acceptance — 9 non-legacy FMs + AmbientDispatcher +
    3 concrete agents discovered + per-function SSE topics."""
    state = await _build_app_state(tmp_path, monkeypatch)
    try:
        # 9 non-legacy FMs (legacy is excluded by init_function_fms);
        # plan floor was "5+", we ship 9 (finance, hr, revenue, ops,
        # legal, marketing, tech, data, customer-success).
        assert len(state.function_fms) >= 5
        for fn_name in (
            "finance", "hr", "revenue", "ops", "legal",
            "marketing", "tech", "data", "customer-success",
        ):
            assert fn_name in state.function_fms, (
                f"function FM missing for {fn_name!r}: have {sorted(state.function_fms)}"
            )
        assert "legacy" not in state.function_fms

        # AmbientDispatcher constructed + the three concrete agents
        # discovered at ``ambient_agents`` package import time.
        assert state.ambient_dispatcher is not None
        from api.server.services.ambient_agents import AMBIENT_AGENTS
        for agent_name in (
            "budget-variance-watcher",
            "vendor-risk-watcher",
            "access-anomaly-watcher",
        ):
            assert agent_name in AMBIENT_AGENTS, (
                f"ambient agent {agent_name!r} not discovered: "
                f"have {sorted(AMBIENT_AGENTS)}"
            )

        # Per-function SSE topics registered on the shared hub.
        # SSEHub has no public ``is_registered``; introspect ``_queues``.
        for fn_name in state.function_fms:
            topic = f"fleet-manager.{fn_name}"
            assert topic in state.hub._queues, (
                f"SSE topic {topic!r} not registered on hub"
            )
    finally:
        await state.aclose()


# ---------------------------------------------------------------------------
# TASK-044 #2 — BusTrigger end-to-end (AccessAnomalyWatcher)
# ---------------------------------------------------------------------------


async def test_ambient_bus_trigger_fires_on_it_access_request_approved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """AccessAnomalyWatcher fires on it-access-request approved completion.

    Note — ``AppState.init_function_fms`` only calls
    ``AmbientDispatcher.start()`` when a running event loop is present
    so unit tests that construct AppState without a loop don't crash.
    Under ``asyncio_mode = auto`` (this test) the loop IS running, so
    start() runs at construction time and the bus subscription is live.
    """
    state = await _build_app_state(tmp_path, monkeypatch)
    try:
        # Override the spawner so we can observe the spawn invocation
        # without depending on the simulator orchestrator + the
        # forward-declared ``access-review`` domain (Phase 4).
        spawn_calls: list[tuple[str, dict]] = []
        state.ambient_dispatcher._spawn_workflow = (
            lambda wt, payload: spawn_calls.append((wt, payload))
        )

        # Emit the trigger event. ``payload`` rides on the FleetEvent
        # via ``model_config = ConfigDict(extra="allow")`` so the
        # dispatcher's ``_safe_dump`` surfaces it for safe-eval filter.
        state.bus.emit(FleetEvent(
            type="workflow.completed",
            workflow_id="WF-IT-SMOKE-1",
            payload={
                "workflow_type": "it-access-request",
                "decision_outcome": {"verdict": "approved"},
            },
        ))

        # ``_handle_bus_trigger`` is sync (driven from ``EventBus.emit``)
        # but its ``_run_sync`` helper schedules ``_spawn_for_agent`` as
        # a Task on the running loop rather than blocking. Yield once so
        # the scheduled task runs before we assert on ``spawn_calls``.
        await asyncio.sleep(0)
        assert any(wt == "access-review" for wt, _ in spawn_calls), (
            "AccessAnomalyWatcher did not fire — "
            f"spawn_calls={spawn_calls}"
        )
    finally:
        await state.aclose()


async def test_ambient_bus_trigger_does_not_fire_on_denied_completion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Filter rejects denied verdicts — guards against false positives."""
    state = await _build_app_state(tmp_path, monkeypatch)
    try:
        spawn_calls: list[tuple[str, dict]] = []
        state.ambient_dispatcher._spawn_workflow = (
            lambda wt, payload: spawn_calls.append((wt, payload))
        )
        state.bus.emit(FleetEvent(
            type="workflow.completed",
            workflow_id="WF-IT-SMOKE-2",
            payload={
                "workflow_type": "it-access-request",
                "decision_outcome": {"verdict": "denied"},
            },
        ))
        await asyncio.sleep(0)
        assert not any(wt == "access-review" for wt, _ in spawn_calls), (
            f"AccessAnomalyWatcher spawned on denied verdict — "
            f"spawn_calls={spawn_calls}"
        )
    finally:
        await state.aclose()


# ---------------------------------------------------------------------------
# TASK-044 #3 — CypherTrigger end-to-end (VendorRiskWatcher)
# ---------------------------------------------------------------------------


async def test_ambient_cypher_trigger_fires_on_high_risk_vendor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """VendorRiskWatcher: a high-risk vendor in the graph triggers
    a vendor-kyc re-screen on the next sweep.

    We bypass the asyncio sleep loop (``sweep_seconds=86400`` would
    deadlock CI) by manually invoking the agent's pattern + the
    dispatcher's spawn helper. This pins the wiring without waiting
    on the production cadence.
    """
    state = await _build_app_state(tmp_path, monkeypatch)
    try:
        from api.server.services.entity_graph import EntityWrite
        state.entities.upsert(EntityWrite(
            kind="Organisation",
            id="ORG-vendor-smoke-high-risk",
            attrs={
                "name": "Test Risky Vendor",
                "kind": "vendor",
                "risk_band": "high",
            },
            source_workflows=("VKY-SMOKE-1",),
        ))

        spawn_calls: list[tuple[str, dict]] = []
        state.ambient_dispatcher._spawn_workflow = (
            lambda wt, payload: spawn_calls.append((wt, payload))
        )

        from api.server.services.ambient_agents import AMBIENT_AGENTS
        agent = AMBIENT_AGENTS["vendor-risk-watcher"]

        # Drive one sweep iteration: pull rows via the agent's
        # CypherTrigger pattern, then call the dispatcher's spawn
        # helper for each row × each spawnable workflow_type.
        cypher_pattern = agent.triggers[0].pattern
        rows = state.entities.query(cypher_pattern)
        assert len(rows) >= 1, (
            f"seeded high-risk vendor not visible to cypher pattern: "
            f"pattern={cypher_pattern!r}, rows={rows}"
        )
        for row in rows:
            await state.ambient_dispatcher._spawn_for_agent(
                agent, base_payload={"trigger": "cypher", "match": row},
            )

        assert any(wt == "vendor-kyc" for wt, _ in spawn_calls), (
            "VendorRiskWatcher did not trigger vendor-kyc — "
            f"spawn_calls={spawn_calls}"
        )
    finally:
        await state.aclose()
