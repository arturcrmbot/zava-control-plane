"""Phase 7 TASK-056 — kill switch end-to-end.

Covers:

- KillSwitchStore primitives: add, remove, list, lazy expiry, wildcard
  semantics, "most-specific wins" lookup.
- Kernel integration (TASK-052): is_killed beats the AGT bundle and
  the registry gate.
- Route round-trip (TASK-053): POST /api/governance/kill, GET /api/governance/kill,
  DELETE /api/governance/kill/{id}, plus the negative cases (missing
  id, ttl <= 0, unknown id).
"""
from __future__ import annotations

import os
import time

# Same Azurite-probe short-circuit as the rest of the governance suite.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import pytest
from fastapi.testclient import TestClient

from api.server.services.governance import GovernanceDenied, kernel
from api.server.services.governance.kernel import _reset_for_tests
from api.server.services.governance.kill_switch import (
    KillSwitch,
    KillSwitchStore,
    kill_switch_store,
    WILDCARD,
)


@pytest.fixture(autouse=True)
def _fresh():
    _reset_for_tests()
    kill_switch_store.clear_for_tests()
    yield
    kill_switch_store.clear_for_tests()
    _reset_for_tests()


# ---------------------------------------------------------------------------
# KillSwitchStore primitives
# ---------------------------------------------------------------------------


class TestKillSwitchStore:
    def test_add_and_list(self) -> None:
        store = KillSwitchStore()
        k1 = store.add("rag-classifier", "claim.lookup", 60.0, "test")
        assert isinstance(k1, KillSwitch)
        assert k1.actor == "rag-classifier"
        assert k1.tool == "claim.lookup"
        assert k1.kill_id
        assert k1.expires_at > k1.created_at
        assert store.list_active() == [k1]

    def test_remove_returns_true_then_false(self) -> None:
        store = KillSwitchStore()
        k = store.add("a", "t", 60.0, "r")
        assert store.remove(k.kill_id) is True
        assert store.remove(k.kill_id) is False
        assert store.list_active() == []

    def test_lazy_expiry(self) -> None:
        store = KillSwitchStore()
        k = store.add("a", "t", 0.001, "r")  # 1ms
        time.sleep(0.005)
        # is_killed and list_active both clean expired kills.
        assert store.is_killed("a", "t") is None
        assert store.list_active() == []

    def test_wildcard_actor_matches_anything(self) -> None:
        store = KillSwitchStore()
        store.add(WILDCARD, "concur.submit_decision", 60.0, "fleet stop")
        assert store.is_killed("any-agent", "concur.submit_decision") is not None
        assert store.is_killed("any-agent", "claim.lookup") is None

    def test_wildcard_tool_matches_anything(self) -> None:
        store = KillSwitchStore()
        store.add("rag-classifier", WILDCARD, 60.0, "pause agent")
        assert store.is_killed("rag-classifier", "any.tool") is not None
        assert store.is_killed("other-agent", "any.tool") is None

    def test_specific_kill_beats_wildcard(self) -> None:
        store = KillSwitchStore()
        wide = store.add(WILDCARD, "claim.lookup", 60.0, "wide")
        time.sleep(0.001)
        narrow = store.add("rag-classifier", "claim.lookup", 60.0, "narrow")
        match = store.is_killed("rag-classifier", "claim.lookup")
        assert match is not None
        assert match.kill_id == narrow.kill_id

    def test_validation_rejects_zero_ttl(self) -> None:
        store = KillSwitchStore()
        with pytest.raises(ValueError):
            store.add("a", "t", 0.0, "r")
        with pytest.raises(ValueError):
            store.add("a", "t", -1.0, "r")

    def test_validation_rejects_empty_actor_or_tool(self) -> None:
        store = KillSwitchStore()
        with pytest.raises(ValueError):
            store.add("", "t", 60.0, "r")
        with pytest.raises(ValueError):
            store.add("a", "", 60.0, "r")


# ---------------------------------------------------------------------------
# Kernel integration (TASK-052)
# ---------------------------------------------------------------------------


class TestKernelHonorsKillSwitch:
    def test_kill_denies_in_log_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGT_ENFORCE", raising=False)
        kill_switch_store.add(
            "rag-classifier", "claim.lookup", 60.0, "operator pause"
        )
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier",
            tool="claim.lookup",  # in allowed_tools, would normally pass
            args={},
        )
        assert decision.allowed is False
        assert decision.rule_id.startswith("kill:")
        assert "operator pause" in decision.reason

    def test_kill_raises_in_enforce(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGT_ENFORCE", "1")
        _reset_for_tests()
        kill_switch_store.add("rag-classifier", "claim.lookup", 60.0, "stop")
        with pytest.raises(GovernanceDenied) as excinfo:
            kernel().evaluate_tool_call(
                actor="rag-classifier",
                tool="claim.lookup",
                args={},
            )
        assert excinfo.value.decision.rule_id.startswith("kill:")

    def test_wildcard_kill_blocks_fleet_wide(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("AGT_ENFORCE", "1")
        _reset_for_tests()
        kill_switch_store.add(WILDCARD, "claim.lookup", 60.0, "fleet stop")
        # Both registered actors get blocked on the same tool.
        for actor in ("rag-classifier", "arbitration"):
            with pytest.raises(GovernanceDenied):
                kernel().evaluate_tool_call(actor=actor, tool="claim.lookup", args={})

    def test_kill_expires_then_call_passes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("AGT_ENFORCE", raising=False)
        kill_switch_store.add("rag-classifier", "claim.lookup", 0.01, "brief")
        time.sleep(0.05)
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier", tool="claim.lookup", args={}
        )
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# Route round-trip (TASK-053)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    return TestClient(app)


class TestKillSwitchRoutes:
    def test_full_lifecycle(self, client) -> None:
        # Empty list to start.
        kill_switch_store.clear_for_tests()
        r = client.get("/api/governance/kill")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["kills"] == []

        # Add one.
        r = client.post(
            "/api/governance/kill",
            json={
                "actor": "rag-classifier",
                "tool": "claim.lookup",
                "ttl_seconds": 60.0,
                "reason": "demo pause",
            },
        )
        assert r.status_code == 200
        body = r.json()
        kill_id = body["kill_id"]
        assert body["actor"] == "rag-classifier"

        # List shows it.
        r = client.get("/api/governance/kill")
        assert r.status_code == 200
        listed = r.json()
        assert listed["total"] == 1
        assert listed["kills"][0]["kill_id"] == kill_id

        # Remove it.
        r = client.delete(f"/api/governance/kill/{kill_id}")
        assert r.status_code == 200
        assert r.json()["removed"] is True

        # List empty again.
        r = client.get("/api/governance/kill")
        assert r.json()["total"] == 0

    def test_post_rejects_zero_ttl(self, client) -> None:
        r = client.post(
            "/api/governance/kill",
            json={
                "actor": "rag-classifier",
                "tool": "claim.lookup",
                "ttl_seconds": 0,
                "reason": "test",
            },
        )
        # Pydantic gt=0 rejects with 422; either is fine.
        assert r.status_code in (400, 422)

    def test_delete_unknown_returns_404(self, client) -> None:
        r = client.delete("/api/governance/kill/no-such-id")
        assert r.status_code == 404

    def test_post_then_kernel_denies(self, client) -> None:
        kill_switch_store.clear_for_tests()
        _reset_for_tests()
        # Add a kill via the route.
        r = client.post(
            "/api/governance/kill",
            json={
                "actor": "rag-classifier",
                "tool": "claim.lookup",
                "ttl_seconds": 60.0,
                "reason": "pause via api",
            },
        )
        assert r.status_code == 200
        # Kernel sees it.
        decision = kernel().evaluate_tool_call(
            actor="rag-classifier", tool="claim.lookup", args={}
        )
        assert decision.allowed is False
        assert decision.rule_id.startswith("kill:")
