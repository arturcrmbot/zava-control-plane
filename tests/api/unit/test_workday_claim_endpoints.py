"""Workday mock — claim-endpoint contract tests.

Drives a locally-launched Express subprocess via httpx. Skipped if Node
isn't installed. Uses WORKDAY_MCP_PORT to avoid clashing with the dev
default (4101).
"""
from __future__ import annotations
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[3]


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


pytestmark = pytest.mark.skipif(
    shutil.which("npx") is None, reason="npx not installed; skipping mock contract tests"
)


@pytest.fixture(scope="module")
def workday_url():
    port = str(_free_port())
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "WORKDAY_MCP_PORT": port}
    # On Windows we need shell=True for npx.cmd resolution
    cmd = ["npx", "tsx", str(ROOT / "mocks" / "workday-mcp" / "server.ts")]
    proc = subprocess.Popen(
        cmd,
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=(sys.platform == "win32"),
    )
    try:
        for _ in range(120):
            try:
                r = httpx.get(f"{url}/mcp/tools", timeout=0.5)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            proc.kill()
            pytest.fail("workday-mcp did not come up on time")
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def test_tools_list_advertises_expense_endpoints(workday_url):
    r = httpx.get(f"{workday_url}/mcp/tools").json()
    names = {t["name"] for t in r["tools"]}
    assert {
        "getExpenseClaim",
        "listClaimsForApproval",
        "submitJustification",
        "listEmployeeClaimHistory",
    } <= names


def test_get_expense_claim_returns_known_claim(workday_url):
    listing = httpx.post(f"{workday_url}/mcp/call/listClaimsForApproval", json={"limit": 1}).json()
    assert listing["claims"], "expected at least one workday claim in the seed"
    claim_id = listing["claims"][0]["claim_id"]
    r = httpx.post(f"{workday_url}/mcp/call/getExpenseClaim", json={"claimId": claim_id}).json()
    assert r["claim_id"] == claim_id
    assert r["ems_source"] == "workday"


def test_get_expense_claim_unknown_returns_404(workday_url):
    r = httpx.post(f"{workday_url}/mcp/call/getExpenseClaim", json={"claimId": "CLM-9999"})
    assert r.status_code == 404


def test_list_claims_for_approval_filters_by_market(workday_url):
    full = httpx.post(f"{workday_url}/mcp/call/listClaimsForApproval", json={"limit": 200}).json()
    markets = {c["market"] for c in full["claims"]}
    assert markets, "expected synthetic claims to cover at least one market"
    pick = next(iter(markets))
    filtered = httpx.post(
        f"{workday_url}/mcp/call/listClaimsForApproval", json={"market": pick, "limit": 200}
    ).json()
    assert filtered["claims"]
    assert all(c["market"] == pick for c in filtered["claims"])


def test_submit_justification_persists_in_memory(workday_url):
    listing = httpx.post(f"{workday_url}/mcp/call/listClaimsForApproval", json={"limit": 1}).json()
    claim_id = listing["claims"][0]["claim_id"]
    body = {"claimId": claim_id, "text": "Client present, named senior stakeholder", "submittedBy": "EMP-0001"}
    r = httpx.post(f"{workday_url}/mcp/call/submitJustification", json=body).json()
    assert r["ok"] is True
    assert "receivedAt" in r
    after = httpx.post(f"{workday_url}/mcp/call/getExpenseClaim", json={"claimId": claim_id}).json()
    assert any(j["text"] == body["text"] for j in after.get("justifications", []))


def test_list_employee_claim_history_returns_breach_summary(workday_url):
    listing = httpx.post(f"{workday_url}/mcp/call/listClaimsForApproval", json={"limit": 5}).json()
    employee_id = listing["claims"][0]["employee_id"]
    r = httpx.post(f"{workday_url}/mcp/call/listEmployeeClaimHistory", json={"employeeId": employee_id}).json()
    assert r["employee_id"] == employee_id
    assert isinstance(r.get("breach_history"), list)
    assert isinstance(r.get("recent_claims"), list)
