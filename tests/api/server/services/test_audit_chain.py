"""Phase 4 TASK-032 — hash-chain end-to-end + tamper detection.

- Log 100 entries across 3 workflows in parallel; verify each chain.
- Mutate one entry's ``details`` field on disk; re-verify; assert
  ``broken_at`` points at the tampered entry.
- The /api/governance/verify/{workflow_id} route returns the same
  VerifyReport JSON as the in-process verify_chain (TASK-030).
"""
from __future__ import annotations

import os

# Same Azurite-probe short-circuit as the rest of the governance suite.
os.environ.setdefault("AZURE_STORAGE_CONNECTION_STRING", "")

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from api.server.services.audit_logger import AuditLogger, VerifyReport


def test_single_workflow_chain_intact() -> None:
    log = AuditLogger()
    for i in range(20):
        log.log("act", {"workflow_id": "WF-1", "i": i})
    report = log.verify_chain("WF-1")
    assert isinstance(report, VerifyReport)
    assert report.chain_intact is True
    assert report.total_entries == 20
    assert report.broken_at is None


def test_unknown_workflow_returns_intact_zero_entries() -> None:
    log = AuditLogger()
    report = log.verify_chain("does-not-exist")
    assert report.chain_intact is True
    assert report.total_entries == 0
    assert report.broken_at is None


def test_two_workflows_have_independent_chains() -> None:
    """PAT-003: chain is per-workflow, not global. Interleaving writes
    on workflow A and workflow B must each produce intact chains."""
    log = AuditLogger()
    for i in range(10):
        log.log("act", {"workflow_id": "A", "i": i})
        log.log("act", {"workflow_id": "B", "i": i})

    a = log.verify_chain("A")
    b = log.verify_chain("B")
    assert a.chain_intact is True and a.total_entries == 10
    assert b.chain_intact is True and b.total_entries == 10

    # Cross-check: A's first entry's prev_hash MUST be genesis, regardless
    # of where it landed in the global insertion order.
    chain_a = log.entries_for("A")
    assert chain_a[0]["prev_hash"] == "0" * 64


def test_parallel_writes_across_three_workflows() -> None:
    """TASK-032 — 100 entries / 3 workflows in parallel. Each chain
    must be intact at the end. Chain locks (per workflow) ensure that
    even with thread contention every prev_hash points correctly."""
    log = AuditLogger()
    workflow_ids = ["W-A", "W-B", "W-C"]
    per_workflow = 33  # 99 entries total — exercises all three chains

    def writer(wid: str) -> None:
        for i in range(per_workflow):
            log.log("parallel", {"workflow_id": wid, "i": i})

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = []
        for wid in workflow_ids:
            futures.append(pool.submit(writer, wid))
            futures.append(pool.submit(writer, wid))  # double up for contention
        for f in futures:
            f.result()

    for wid in workflow_ids:
        report = log.verify_chain(wid)
        assert report.chain_intact is True, f"{wid}: {report.reason}"
        assert report.total_entries == per_workflow * 2


def test_tamper_detection_returns_broken_at() -> None:
    log = AuditLogger()
    for i in range(5):
        log.log("act", {"workflow_id": "WF-T", "i": i})

    chain = log.entries_for("WF-T")
    assert len(chain) == 5

    # Mutate index 2 in place. The hash chain MUST detect this.
    chain[2]["details"] = {"workflow_id": "WF-T", "i": "TAMPERED"}

    report = log.verify_chain("WF-T")
    assert report.chain_intact is False
    assert report.broken_at == 2
    assert report.reason and "mismatch" in report.reason


def test_tamper_at_first_entry_detected() -> None:
    log = AuditLogger()
    for i in range(3):
        log.log("act", {"workflow_id": "WF-FIRST", "i": i})

    log.entries_for("WF-FIRST")[0]["timestamp"] = 0.0
    report = log.verify_chain("WF-FIRST")
    assert report.chain_intact is False
    assert report.broken_at == 0


def test_tamper_at_last_entry_detected() -> None:
    log = AuditLogger()
    for i in range(3):
        log.log("act", {"workflow_id": "WF-LAST", "i": i})

    log.entries_for("WF-LAST")[-1]["details"] = {"workflow_id": "WF-LAST", "evil": True}
    report = log.verify_chain("WF-LAST")
    assert report.chain_intact is False
    assert report.broken_at == 2


def test_chain_starts_from_genesis_hash() -> None:
    log = AuditLogger()
    log.log("first", {"workflow_id": "WF-G"})
    chain = log.entries_for("WF-G")
    assert chain[0]["prev_hash"] == "0" * 64
    assert len(chain[0]["entry_hash"]) == 64  # sha256 hex


# ---------------------------------------------------------------------------
# TASK-030 — /api/governance/verify/{workflow_id} route
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    from api.server.main import app
    return TestClient(app)


def test_verify_route_returns_intact_report_for_unknown_workflow(client) -> None:
    r = client.get("/api/governance/verify/UNKNOWN-WORKFLOW-1234")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == "UNKNOWN-WORKFLOW-1234"
    assert body["chain_intact"] is True
    assert body["total_entries"] == 0
    assert body["broken_at"] is None


def test_verify_route_reflects_real_chain_state(client) -> None:
    """Logging via the AppState audit logger should be visible to the
    route on the same process. Uses a unique workflow id so the test
    is order-independent."""
    from api.server.state import app_state

    wid = f"WF-ROUTE-{threading.get_ident()}"
    for i in range(4):
        app_state.audit.log("act", {"workflow_id": wid, "i": i})

    r = client.get(f"/api/governance/verify/{wid}")
    assert r.status_code == 200
    body = r.json()
    assert body["workflow_id"] == wid
    assert body["chain_intact"] is True
    assert body["total_entries"] == 4

    # Tamper and re-fetch.
    app_state.audit.entries_for(wid)[1]["details"] = {"workflow_id": wid, "x": "evil"}
    r2 = client.get(f"/api/governance/verify/{wid}")
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["chain_intact"] is False
    assert body2["broken_at"] == 1


def test_verify_route_rejects_blank_workflow_id(client) -> None:
    """A whitespace-only id is treated as missing. Path matching makes
    a truly empty path part 404 by FastAPI before we see it; assert the
    explicit guard for whitespace via percent-encoded space."""
    r = client.get("/api/governance/verify/%20")
    assert r.status_code == 404
