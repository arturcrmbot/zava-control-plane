"""Concur mock — claim-endpoint contract tests.

Drives a locally-launched Express subprocess via httpx. Skipped if Node
isn't installed. Uses CONCUR_MCP_PORT to avoid clashing with the dev
default (4102).
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

BEARER = {"Authorization": "Bearer test-token"}


@pytest.fixture(scope="module")
def concur_url():
    port = str(_free_port())
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "CONCUR_MCP_PORT": port}
    cmd = ["npx", "tsx", str(ROOT / "mocks" / "concur-mcp" / "server.ts")]
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
                r = httpx.get(f"{url}/mcp/tools", headers=BEARER, timeout=0.5)
                if r.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.25)
        else:
            proc.kill()
            pytest.fail("concur-mcp did not come up on time")
        yield url
    finally:
        proc.kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def test_oauth_required(concur_url):
    """Requests without a Bearer token are rejected 401."""
    r = httpx.get(f"{concur_url}/mcp/tools", timeout=2.0)
    assert r.status_code == 401


def test_oauth_token_endpoint(concur_url):
    r = httpx.post(
        f"{concur_url}/oauth/token",
        json={"grant_type": "client_credentials"},
        headers=BEARER,
        timeout=2.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "Bearer"
    assert body["access_token"].startswith("concur-mock-token-")


def test_lists_advertised_tools(concur_url):
    r = httpx.get(f"{concur_url}/mcp/tools", headers=BEARER, timeout=2.0)
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert names == {
        "listExpenseReports", "getExpenseLine", "getReceipt", "submitJustification",
    }


def test_list_expense_reports_filtered_by_market(concur_url):
    r = httpx.post(
        f"{concur_url}/mcp/call/listExpenseReports",
        json={"market": "US", "limit": 5},
        headers=BEARER,
        timeout=2.0,
    )
    assert r.status_code == 200
    reports = r.json()["reports"]
    assert 0 < len(reports) <= 5
    # Reports use Concur's idiomatic field names
    sample = reports[0]
    assert {"reportItemId", "submitter", "totalAmount", "currencyCode", "submittedAt", "status"} <= set(sample)


def test_get_expense_line_returns_normalised_under_key(concur_url):
    """getExpenseLine wraps the original synthetic record under `_normalised`
    so the Python claim_lookup adapter can unwrap and normalise across both EMSs."""
    list_r = httpx.post(
        f"{concur_url}/mcp/call/listExpenseReports",
        json={"limit": 1}, headers=BEARER, timeout=2.0,
    )
    assert list_r.status_code == 200
    cid = list_r.json()["reports"][0]["reportItemId"]

    r = httpx.post(
        f"{concur_url}/mcp/call/getExpenseLine",
        json={"reportItemId": cid}, headers=BEARER, timeout=2.0,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reportItemId"] == cid
    assert "_normalised" in body
    assert body["_normalised"]["claim_id"] == cid
    assert body["_normalised"]["ems_source"] == "concur"


def test_submit_justification_round_trip(concur_url):
    list_r = httpx.post(
        f"{concur_url}/mcp/call/listExpenseReports",
        json={"limit": 1}, headers=BEARER, timeout=2.0,
    )
    cid = list_r.json()["reports"][0]["reportItemId"]
    r = httpx.post(
        f"{concur_url}/mcp/call/submitJustification",
        json={
            "reportItemId": cid,
            "text": "Client dinner with Senior VP, named attendees attached.",
            "submittedBy": "EMP-test",
        },
        headers=BEARER,
        timeout=2.0,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
