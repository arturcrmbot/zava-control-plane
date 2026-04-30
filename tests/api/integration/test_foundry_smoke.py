"""Real-Foundry smoke test: 5 hand-picked claims through batch_runner.

Skipped automatically without creds. Run as:
  pytest tests/api/integration/test_foundry_smoke.py -m foundry -v
"""
from __future__ import annotations
import os

import pytest


pytestmark = pytest.mark.foundry


def _has_creds() -> bool:
    return all(os.environ.get(k) for k in (
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "AZURE_FOUNDRY_JUDGE_MODEL_DEPLOYMENT",
    ))


@pytest.mark.skipif(not _has_creds(), reason="Foundry creds not set")
@pytest.mark.asyncio
async def test_foundry_smoke_5_claims():
    from api.server.eval.batch_runner import run

    from pathlib import Path
    claims_dir = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "claims"
    available = sorted(p.stem for p in claims_dir.glob("CLM-*.json"))[:5]
    assert len(available) == 5, "need at least 5 synthetic claims for the smoke run"

    captured: list[dict] = []
    report = await run(claim_ids=available, run_id="smoke-test",
                       publish=lambda e: captured.append(e))

    assert report["n"] == 5
    assert "overall_accuracy" in report
    assert isinstance(report["overall_accuracy"], float)
    assert 0.0 <= report["overall_accuracy"] <= 1.0
    assert "confusion_matrix" in report
    assert report.get("foundry_run_url"), "expected studio_url from Foundry"
    types = [e.get("type") for e in captured]
    assert "accuracy.progress" in types
    assert "accuracy.complete" in types
